# routers/cuentas_clientes.py
#
# Lado STAFF de la validación de acceso al Portal del Cliente / App Móvil.
# Solo Administrador o Contador Gerente pueden aprobar/rechazar — según lo
# definido para este flujo (un cliente no puede autoaprobarse, y tampoco
# cualquier empleado: se reserva a los niveles de mayor responsabilidad).
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from schemas import SolicitudCuentaResponse, RechazoSolicitud
from security import requiere_rol

router = APIRouter(
    prefix="/cuentas-clientes",
    tags=["Validación de Acceso al Portal del Cliente"]
)

ROLES_VALIDADORES = ("Administrador", "Contador Gerente")


@router.get("/", response_model=List[SolicitudCuentaResponse])
def listar_solicitudes(estatus: Optional[str] = None, db=Depends(get_db), _=Depends(requiere_rol(*ROLES_VALIDADORES))):
    query = db.table("cuentas_clientes").select("*")
    if estatus:
        # Permite filtrar por ejemplo "?estatus=Pendiente" para ver solo
        # lo que falta por revisar, sin traer todo el historial completo.
        query = query.eq("estatus_solicitud", estatus)
    respuesta = query.order("fecha_solicitud", desc=True).execute()
    return respuesta.data


@router.patch("/{solicitud_id}/aprobar", response_model=SolicitudCuentaResponse)
def aprobar_solicitud(solicitud_id: int, db=Depends(get_db), _=Depends(requiere_rol(*ROLES_VALIDADORES))):
    respuesta = db.table("cuentas_clientes").update({
        "estatus_solicitud": "Aprobada",
        "motivo_rechazo": None,
    }).eq("id", solicitud_id).execute()

    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    return respuesta.data[0]


@router.patch("/{solicitud_id}/rechazar", response_model=SolicitudCuentaResponse)
def rechazar_solicitud(solicitud_id: int, rechazo: RechazoSolicitud, db=Depends(get_db), _=Depends(requiere_rol(*ROLES_VALIDADORES))):
    respuesta = db.table("cuentas_clientes").update({
        "estatus_solicitud": "Rechazada",
        "motivo_rechazo": rechazo.motivo_rechazo,
    }).eq("id", solicitud_id).execute()

    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    return respuesta.data[0]
