# routers/portal_cliente.py
#
# Rutas usadas por la App Móvil (React Native/Expo) del lado del CLIENTE,
# no del personal. Cubre 3 momentos distintos:
#   1. Solicitar cuenta (público — el cliente todavía no puede loguearse)
#   2. Consultar el estatus de esa solicitud (público, sin token)
#   3. Login + consultar trámite / gestionar sus propias citas (con token
#      de tipo "cliente", emitido aquí mismo tras un login exitoso)
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from database import get_db
from schemas import (
    SolicitudCuentaCreate, SolicitudCuentaResponse,
    ClienteLoginSchema, ClienteTokenResponse,
    MiTramiteResponse, CitaResponse, CitaClienteCreate,
)
from security import hash_password, verificar_password, crear_token_acceso, obtener_cliente_actual

router = APIRouter(
    prefix="/portal-cliente",
    tags=["Portal del Cliente (App Móvil)"]
)


@router.post("/solicitar-cuenta", response_model=SolicitudCuentaResponse)
def solicitar_cuenta(solicitud: SolicitudCuentaCreate, db=Depends(get_db)):
    """
    El cliente ya fue registrado internamente por Marketing/Secretaria (ver
    leads.py, clientes.py) — aquí solo pide ACCESO DIGITAL a ese registro.
    Por eso el teléfono tiene que coincidir con un Cliente que ya exista;
    si no, cualquiera podría inventar una cuenta sin ser cliente real.
    """
    cliente_existente = db.table("clientes").select("id, nombre").eq("telefono", solicitud.telefono).execute()
    if not cliente_existente.data:
        raise HTTPException(
            status_code=404,
            detail="No encontramos ningún cliente registrado con ese teléfono. "
                   "Contacta a un asesor para que primero te registre en el sistema."
        )
    cliente_id = cliente_existente.data[0]["id"]

    # ¿Ya existe una solicitud previa con este teléfono?
    solicitud_previa = db.table("cuentas_clientes").select("*").eq("telefono", solicitud.telefono).execute()

    datos = {
        "cliente_id": cliente_id,
        "telefono": solicitud.telefono,
        "correo": solicitud.correo,
        "contrasena": hash_password(solicitud.contrasena),
        "estatus_solicitud": "Pendiente",
        "motivo_rechazo": None,
        "fecha_solicitud": datetime.now(timezone.utc).isoformat(),
    }

    if solicitud_previa.data:
        estatus_previo = solicitud_previa.data[0]["estatus_solicitud"]
        if estatus_previo in ("Pendiente", "Aprobada"):
            # No dejamos crear una solicitud duplicada mientras la anterior
            # sigue vigente (pendiente de revisión o ya aprobada).
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe una solicitud con estatus '{estatus_previo}' para este teléfono."
            )
        # Si la anterior fue Rechazada, permitimos reintentar: actualizamos
        # la MISMA fila en vez de crear una nueva (evita ir acumulando
        # solicitudes viejas sin sentido).
        respuesta = db.table("cuentas_clientes").update(datos).eq("id", solicitud_previa.data[0]["id"]).execute()
    else:
        respuesta = db.table("cuentas_clientes").insert(datos).execute()

    return respuesta.data[0]


@router.get("/estatus-solicitud/{telefono}", response_model=SolicitudCuentaResponse)
def consultar_estatus_solicitud(telefono: str, db=Depends(get_db)):
    """
    Ruta pública (sin token — el cliente todavía no tiene uno) para que la
    app pueda mostrar "tu solicitud está pendiente / fue aprobada / fue
    rechazada por tal motivo" antes de poder loguearse.
    """
    respuesta = db.table("cuentas_clientes").select("*").eq("telefono", telefono).execute()
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="No hay ninguna solicitud de cuenta con ese teléfono.")
    return respuesta.data[0]


@router.post("/login", response_model=ClienteTokenResponse)
def login_cliente(credenciales: ClienteLoginSchema, db=Depends(get_db)):
    cuenta = db.table("cuentas_clientes").select("*").eq("telefono", credenciales.telefono).execute()
    if not cuenta.data:
        raise HTTPException(status_code=401, detail="Ese teléfono no tiene ninguna cuenta solicitada.")

    cuenta = cuenta.data[0]

    if cuenta["estatus_solicitud"] != "Aprobada":
        # Cortamos aquí ANTES de siquiera revisar la contraseña: no tiene
        # sentido dejar loguearse a alguien cuya cuenta no está aprobada,
        # sin importar si la contraseña es correcta.
        raise HTTPException(
            status_code=403,
            detail=f"Tu cuenta todavía no está aprobada (estatus actual: {cuenta['estatus_solicitud']})."
        )

    if not verificar_password(credenciales.contrasena, cuenta["contrasena"]):
        raise HTTPException(status_code=401, detail="Contraseña incorrecta.")

    cliente_info = db.table("clientes").select("nombre").eq("id", cuenta["cliente_id"]).execute()
    nombre_cliente = cliente_info.data[0]["nombre"] if cliente_info.data else ""

    token = crear_token_acceso({
        "telefono": cuenta["telefono"],
        "cliente_id": cuenta["cliente_id"],
        "tipo": "cliente",
        # OJO: "rol" no aplica aquí — los clientes no tienen roles internos
        # como el personal (RolSistema). El único "permiso" que existe en
        # este lado es ser dueño de su propio cliente_id.
    })

    return ClienteTokenResponse(access_token=token, cliente_id=cuenta["cliente_id"], nombre=nombre_cliente)


@router.get("/mi-tramite", response_model=MiTramiteResponse)
def consultar_mi_tramite(db=Depends(get_db), cliente_actual=Depends(obtener_cliente_actual)):
    """
    El cliente_id NUNCA viene de la petición — viene del token ya
    verificado (cliente_actual['cliente_id']). Así, un cliente jamás puede
    consultar el trámite de otro cambiando un número en la URL: solo puede
    ver lo que su propio token le permite.
    """
    cliente_id = cliente_actual["cliente_id"]

    cliente = db.table("clientes").select("estatus_expediente").eq("id", cliente_id).execute()
    if not cliente.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    documentos = db.table("transacciones").select("tipo_documento, estado, fecha_registro").eq("cliente_id", cliente_id).execute()
    facturas = db.table("facturas").select("numero_operacion, servicio, costo, fecha").eq("cliente_id", cliente_id).execute()

    return MiTramiteResponse(
        estatus_expediente=cliente.data[0]["estatus_expediente"],
        documentos=documentos.data,
        facturas=facturas.data,
    )


@router.post("/mis-citas", response_model=CitaResponse)
def solicitar_mi_cita(datos_cita: CitaClienteCreate, db=Depends(get_db), cliente_actual=Depends(obtener_cliente_actual)):
    # Recibimos solo "motivo" y "fecha_solicitud" del cliente — el
    # cliente_id se fija aquí mismo desde el token, nunca desde lo que
    # mande la app (mismo principio que en consultar_mi_tramite).
    nueva_cita = {
        "cliente_id": cliente_actual["cliente_id"],
        "motivo": datos_cita.motivo,
        "fecha_solicitud": datos_cita.fecha_solicitud.isoformat(),
        "confirmada": False,
    }
    respuesta = db.table("citas").insert(nueva_cita).execute()
    return respuesta.data[0]


@router.get("/mis-citas", response_model=List[CitaResponse])
def obtener_mis_citas(db=Depends(get_db), cliente_actual=Depends(obtener_cliente_actual)):
    respuesta = db.table("citas").select("*").eq("cliente_id", cliente_actual["cliente_id"]).execute()
    return respuesta.data
