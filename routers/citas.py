# ============================================================================
# routers/citas.py
#
# QUÉ HACE ESTE ARCHIVO, EN UNA FRASE:
# Permite a la Secretaria programar y confirmar citas de clientes. No forma
# parte del DFD original — se integró como módulo adicional del sistema.
#
# NOTA PARA EL DOCUMENTO: para que el proyecto quede 100% coherente, conviene
# reflejar este módulo también en el DFD (como un sub-flujo dentro del Proceso 2
# o 5, con su propio almacén "A5 Citas") y en el diagrama de clases (una clase
# Cita asociada a Cliente). El código ya está listo para eso; falta el lado
# de la documentación.
# ============================================================================
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from schemas import CitaCreate, CitaResponse
from security import requiere_rol, obtener_usuario_actual

router = APIRouter(
    prefix="/citas",
    tags=["Gestión de Citas (integrado — Secretaria)"]
)


@router.post("/", response_model=CitaResponse, dependencies=[
    Depends(requiere_rol("Secretaria", "Administrador"))
])
def programar_cita(cita: CitaCreate, db=Depends(get_db)):
    # Solo Secretaria (o Administrador) puede programar citas — coincide
    # con lo que dice el organigrama: la gestión de agenda es tarea de
    # Secretaria.
    datos = cita.model_dump()
    datos["confirmada"] = False
    # Toda cita nueva empieza como NO confirmada. Alguien de Secretaria
    # tiene que confirmarla explícitamente más adelante (ver la ruta de
    # abajo).

    respuesta = db.table("citas").insert(datos).execute()
    return respuesta.data[0]


@router.get("/", response_model=List[CitaResponse])
def obtener_citas(db=Depends(get_db), _=Depends(obtener_usuario_actual)):
    # Cualquier empleado con sesión iniciada puede CONSULTAR las citas
    # (no solo Secretaria) — por ejemplo, un Contador podría querer ver
    # si hay una cita programada relacionada con un cliente que está
    # atendiendo.
    respuesta = db.table("citas").select("*").execute()
    return respuesta.data


@router.patch("/{cita_id}/confirmar", response_model=CitaResponse, dependencies=[
    Depends(requiere_rol("Secretaria", "Administrador"))
])
# PATCH es el método HTTP que se usa quando solo se va a modificar UNA
# PARTE de un registro que ya existe (aquí, solo el campo "confirmada"),
# a diferencia de POST que es para crear algo nuevo.
def confirmar_cita(cita_id: int, db=Depends(get_db)):
    respuesta = db.table("citas").update({"confirmada": True}).eq("id", cita_id).execute()
    # "update({...}).eq(...)" significa: "en la fila donde el id
    # coincida, cambia el valor de la columna 'confirmada' a True — deja
    # todas las demás columnas como estaban".

    if not respuesta.data:
        # Si Supabase no encontró ninguna fila con ese id para actualizar,
        # la lista de resultados viene vacía.
        raise HTTPException(status_code=404, detail="Cita no encontrada.")
    return respuesta.data[0]
