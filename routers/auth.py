# routers/auth.py
from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from schemas import LoginSchema, TokenResponse, UsuarioCreate, UsuarioResponse
from security import hash_password, verificar_password, crear_token_acceso, requiere_rol

router = APIRouter(
    prefix="/auth",
    tags=["Autenticación y Control de Acceso"]
)


@router.post("/login", response_model=TokenResponse)
def iniciar_sesion(credenciales: LoginSchema, db=Depends(get_db)):
    response = db.table("usuarios").select("*").eq("usuario", credenciales.usuario).execute()

    if not response.data:
        raise HTTPException(status_code=401, detail="El nombre de usuario no coincide con nuestros registros.")

    usuario_encontrado = response.data[0]

    # Antes: comparación en texto plano ("if usuario_encontrado['contrasena'] != credenciales.contrasena").
    # Ahora: verificación contra el hash bcrypt guardado.
    if not verificar_password(credenciales.contrasena, usuario_encontrado["contrasena"]):
        raise HTTPException(status_code=401, detail="La contraseña ingresada es incorrecta.")

    token = crear_token_acceso({
        "usuario": usuario_encontrado["usuario"],
        "rol": usuario_encontrado["rol"],
        "tipo": "staff",
    })

    return TokenResponse(
        access_token=token,
        usuario=usuario_encontrado["usuario"],
        rol=usuario_encontrado["rol"],
    )


@router.post("/registrar", response_model=UsuarioResponse, dependencies=[Depends(requiere_rol("Administrador"))])
def registrar_personal(nuevo_usuario: UsuarioCreate, db=Depends(get_db)):
    """
    Antes esta ruta no tenía NINGUNA protección: cualquiera podía crear una
    cuenta 'Administrador' llamando la API directamente, sin pasar por el login.
    Ahora requiere un token válido de un usuario que YA sea Administrador.
    """
    existente = db.table("usuarios").select("usuario").eq("usuario", nuevo_usuario.usuario).execute()
    if existente.data:
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya existe.")

    datos_para_guardar = nuevo_usuario.model_dump()
    datos_para_guardar["contrasena"] = hash_password(nuevo_usuario.contrasena)

    db.table("usuarios").insert(datos_para_guardar).execute()

    return UsuarioResponse(
        usuario=nuevo_usuario.usuario,
        rol=nuevo_usuario.rol,
        nombre_completo=nuevo_usuario.nombre_completo,
    )
