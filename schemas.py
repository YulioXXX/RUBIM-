# schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime

# --- ROLES DEL SISTEMA ---
# Alineados con el organigrama y los procesos del DFD (antes el dropdown de
# "Crear Acceso" solo tenía Secretaria/Asistente/Auxiliar Contable/Contable/
# Administrador, y no calzaban con los actores reales del DFD/diagrama de clases).
RolSistema = Literal[
    "Administrador",          # Gerencia general / control total
    "Asesor de Marketing",    # Proceso 1: Captación de Leads
    "Secretaria",             # Proceso 2 y 5: Registrar/asignar canal, Consultar y entregar, Citas
    "Contador Auxiliar",      # Proceso 3: Recibir y almacenar documentos
    "Contador Junior",        # Proceso 4: Gestionar contabilidad
    "Contador Senior",        # Proceso 4: Gestionar contabilidad (validación final)
    "Contador Gerente",       # Proceso 4: Gestionar contabilidad (supervisión)
    "Asesor Financiero",      # Proceso 6: Facturación de Servicios
]


# --- ESQUEMAS PARA USUARIOS / STAFF (antes no existían formalmente) ---
class UsuarioCreate(BaseModel):
    usuario: str
    contrasena: str = Field(min_length=6)
    rol: RolSistema
    nombre_completo: Optional[str] = None


class UsuarioResponse(BaseModel):
    usuario: str
    rol: RolSistema
    nombre_completo: Optional[str] = None
    # OJO: nunca se incluye 'contrasena' ni su hash en las respuestas.


# --- ESQUEMAS DE AUTENTICACIÓN ---
class LoginSchema(BaseModel):
    usuario: str
    contrasena: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: str
    rol: RolSistema


# --- ESQUEMAS PARA LEADS (Proceso 1: Captación de Leads) ---
# Corresponde a los flujos (1)-(4) del DFD: el prospecto todavía no es cliente
# formal, solo se capturan sus datos de contacto e interés.
class LeadCreate(BaseModel):
    nombre_prospecto: str
    telefono: str
    correo: Optional[str] = None
    servicio_interes: str


class LeadResponse(LeadCreate):
    id: int
    fecha_registro: datetime
    convertido: bool = False


# --- ESQUEMAS PARA CLIENTES (Proceso 2, almacén A1) ---
class ClienteBase(BaseModel):
    nombre: str
    tipo_cliente: Literal["Industriales", "Comerciantes", "Particulares"]
    telefono: Optional[str] = None
    # 'canal' ya NO se recibe del formulario: lo calcula el backend (ver routers/leads.py
    # y routers/clientes.py) siguiendo la regla de negocio real del DFD, en vez de
    # confiar en un <input readonly> del frontend que cualquiera puede editar
    # directamente en el DOM o llamando la API a mano.


class ClienteCreate(ClienteBase):
    lead_id: Optional[int] = None  # si viene de un lead convertido


class ClienteResponse(ClienteBase):
    id: int
    canal: str
    estatus_expediente: str

    class Config:
        from_attributes = True


# --- ESQUEMAS PARA EXPEDIENTES / TRANSACCIONES (Proceso 3 y 4, almacén A2) ---
class TransaccionBase(BaseModel):
    tipo_documento: str
    procesado_por: Optional[str] = None
    estado: Literal["Pendiente", "En revisión", "Completado"] = "Pendiente"


class TransaccionCreate(TransaccionBase):
    cliente_id: int


class TransaccionResponse(TransaccionBase):
    id: int
    cliente_id: int
    fecha_registro: datetime

    class Config:
        from_attributes = True


# --- ESQUEMAS PARA CITAS (integrado formalmente, gestionado por Secretaria) ---
class CitaBase(BaseModel):
    motivo: str
    fecha_solicitud: datetime


class CitaCreate(CitaBase):
    cliente_id: int


class CitaResponse(CitaBase):
    id: int
    cliente_id: int
    confirmada: bool

    class Config:
        from_attributes = True


# --- ESQUEMAS PARA FACTURAS (Proceso 6, almacén A4 — no existía en el código) ---
class FacturaBase(BaseModel):
    servicio: str
    costo: float = Field(gt=0)


class FacturaCreate(FacturaBase):
    cliente_id: int
    transaccion_id: Optional[int] = None  # expediente/trámite que originó el cobro


class FacturaResponse(FacturaBase):
    id: int
    cliente_id: int
    numero_operacion: str
    fecha: datetime

    class Config:
        from_attributes = True


# ----------------------------------------------------------------------------
# PORTAL DEL CLIENTE (App Móvil) — solicitud de cuenta y acceso
# ----------------------------------------------------------------------------
# El cliente YA existe como registro interno (fue capturado por Marketing/
# Secretaria, ver leads.py y clientes.py). Esto es una capa aparte: la
# CUENTA DE ACCESO a la app móvil, que empieza "Pendiente" hasta que un
# Administrador o Contador Gerente la aprueba desde el panel web.

EstatusSolicitud = Literal["Pendiente", "Aprobada", "Rechazada"]


class SolicitudCuentaCreate(BaseModel):
    # Lo que manda la app móvil cuando alguien pide abrir su cuenta.
    telefono: str
    contrasena: str = Field(min_length=6)
    correo: Optional[str] = None


class SolicitudCuentaResponse(BaseModel):
    id: int
    cliente_id: int
    telefono: str
    correo: Optional[str] = None
    estatus_solicitud: EstatusSolicitud
    motivo_rechazo: Optional[str] = None
    fecha_solicitud: datetime

    class Config:
        from_attributes = True


class RechazoSolicitud(BaseModel):
    # Lo que manda el staff al rechazar, para darle al cliente un motivo
    # claro (y que pueda corregir y volver a solicitar).
    motivo_rechazo: str


class ClienteLoginSchema(BaseModel):
    # Igual que LoginSchema, pero del lado del cliente — mismo concepto,
    # esquema separado porque conceptualmente son dos mundos distintos.
    telefono: str
    contrasena: str


class ClienteTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    cliente_id: int
    nombre: str


class MiTramiteResponse(BaseModel):
    # Lo que ve el cliente al consultar el estatus de "su" trabajo — una
    # combinación resumida de su expediente, no la tabla cruda completa.
    estatus_expediente: str
    documentos: List[dict]
    facturas: List[dict]


class CitaClienteCreate(BaseModel):
    # Igual que CitaCreate, pero SIN cliente_id — el cliente nunca debe
    # poder elegir para qué cliente_id es la cita (ver portal_cliente.py:
    # ese valor se toma directo del token, no de lo que mande la app).
    motivo: str
    fecha_solicitud: datetime
