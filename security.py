# security.py
# Módulo central de seguridad para el TPS de RUBIM.
# Resuelve 3 huecos que tenía el sistema original:
#   1) Contraseñas guardadas y comparadas en texto plano.
#   2) Ninguna verificación de identidad en las rutas protegidas (todo dependía
#      de una variable en localStorage, manipulable desde la consola del navegador).
#   3) Sin expiración de sesión.

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))

if not SECRET_KEY:
    raise RuntimeError(
        "Falta JWT_SECRET_KEY en el entorno. Configura tu archivo .env "
        "(ver .env.example) antes de levantar el servidor."
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# apunta a /auth/login solo para que Swagger UI (/docs) sepa dónde autenticar;
# no exige que el login use form-data, seguimos aceptando JSON.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


# --- Contraseñas ---

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verificar_password(password_plano: str, password_hash: str) -> bool:
    return pwd_context.verify(password_plano, password_hash)


# --- Tokens JWT ---

def crear_token_acceso(datos: dict, expires_minutes: Optional[int] = None) -> str:
    """Genera un JWT firmado con el usuario, su rol y una fecha de expiración."""
    payload = datos.copy()
    expira = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or EXPIRE_MINUTES
    )
    payload.update({"exp": expira})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decodificar_token(token: str) -> dict:
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada. Vuelve a iniciar sesión.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("usuario") is None:
            raise credenciales_invalidas
        return payload
    except JWTError:
        raise credenciales_invalidas


def obtener_usuario_actual(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency: extrae y valida el JWT del header Authorization: Bearer <token>."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se envió token de sesión. Inicia sesión primero.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decodificar_token(token)

    # IMPORTANTE (agregado junto con el Portal del Cliente / App Móvil):
    # ahora existen DOS tipos de token en el sistema — uno para personal
    # (staff, generado en routers/auth.py) y otro para clientes de la app
    # móvil (generado en routers/portal_cliente.py). Sin esta verificación,
    # un cliente autenticado en la app podría usar SU token válido para
    # llamar rutas del panel interno (ej. GET /clientes/) y ver datos de
    # TODOS los clientes de la firma, no solo los suyos. Por eso toda ruta
    # de personal (esta dependency, y por extensión requiere_rol()) exige
    # explícitamente que el token sea de tipo "staff".
    if payload.get("tipo") != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este token no corresponde a una cuenta de personal.",
        )

    return {"usuario": payload["usuario"], "rol": payload["rol"]}


def obtener_cliente_actual(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency equivalente a obtener_usuario_actual, pero para el lado del
    Portal del Cliente (la App Móvil). Exige un token de tipo "cliente" —
    un token de personal (Administrador, Secretaria, etc.) NO sirve aquí,
    por la misma razón inversa a la de arriba: separar completamente los
    dos mundos, para que ni el personal pueda hacerse pasar por un cliente
    ni viceversa.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se envió token de sesión. Inicia sesión en la app primero.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decodificar_token(token)

    if payload.get("tipo") != "cliente":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este token no corresponde a una cuenta de cliente.",
        )

    # Devolvemos el cliente_id — es la pieza clave que hace que cada
    # cliente SOLO pueda ver/crear información propia: cada ruta del
    # portal usa este cliente_id (que viene firmado dentro del token, así
    # que no se puede falsificar) en vez de confiar en un cliente_id que
    # el propio cliente pudiera escribir a mano en la petición.
    return {"cliente_id": payload["cliente_id"], "telefono": payload["telefono"]}


def requiere_rol(*roles_permitidos: str):
    """
    Dependency factory para proteger rutas por rol, ej:
        @router.post("/", dependencies=[Depends(requiere_rol("Administrador"))])

    Esto es lo que faltaba por completo en el sistema original: la verificación
    de rol vivía solo en el frontend (localStorage), así que cualquiera podía
    llamar la API directamente y saltarse el control.
    """
    def verificador(usuario_actual: dict = Depends(obtener_usuario_actual)) -> dict:
        if usuario_actual["rol"] not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu rol ({usuario_actual['rol']}) no tiene permiso para esta acción.",
            )
        return usuario_actual
    return verificador
