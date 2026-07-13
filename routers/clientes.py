# ============================================================================
# routers/clientes.py
#
# QUÉ HACE ESTE ARCHIVO, EN UNA FRASE:
# Registra clientes de forma directa (sin pasar por la etapa de lead) y
# permite consultarlos. Corresponde al Proceso 2 del DFD y al almacén A1.
# ============================================================================
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from schemas import ClienteCreate, ClienteResponse
from security import requiere_rol, obtener_usuario_actual

router = APIRouter(
    prefix="/clientes",
    tags=["Gestión de Clientes (Proceso 2, almacén A1)"]
)


def _asignar_canal(tipo_cliente: str) -> str:
    # La MISMA regla de negocio que en leads.py. Está repetida aquí a
    # propósito porque este archivo puede registrar un cliente SIN pasar
    # por el flujo de leads (por ejemplo, un cliente que llega en
    # persona y se registra directo con la Secretaria).
    if tipo_cliente in ("Industriales", "Comerciantes"):
        return "Canales Altos"
    return "Canales Bajos"


@router.post("/", response_model=ClienteResponse, dependencies=[
    Depends(requiere_rol("Secretaria", "Asesor de Marketing", "Administrador"))
])
# Aquí SÍ exigimos rol — a diferencia de la captura de leads, registrar
# un Cliente formal ya es una acción que debe hacer un empleado
# autorizado, no un visitante externo.
def registrar_cliente(cliente: ClienteCreate, db=Depends(get_db)):
    """
    Registro directo de cliente (walk-in sin pasar por /leads/), a cargo de
    Secretaria — Proceso 2 del DFD.
    """
    datos = cliente.model_dump(exclude={"lead_id"})
    # .model_dump(exclude={"lead_id"}) convierte el objeto a diccionario
    # PERO excluyendo el campo "lead_id" — ese campo es solo informativo
    # para cuando el cliente viene de un lead ya convertido (ver
    # leads.py), no es una columna real que se guarde en la tabla
    # "clientes" en este flujo directo.

    datos["canal"] = _asignar_canal(cliente.tipo_cliente)  # ya no viene del frontend
    datos["estatus_expediente"] = "En revisión"
    # Todo cliente nuevo arranca con su expediente "En revisión" — el
    # Proceso 3/4 (Contadores) se encargará de avanzarlo después.

    # Antes: "data, count = db.table(...).insert(...).execute()" — ese patrón de
    # unpacking es de una versión muy vieja de supabase-py/postgrest-py y no
    # funciona con el cliente supabase-py actual (APIResponse no es una tupla
    # (str, valor) iterable de esa forma). Ahora se usa response.data directamente.
    respuesta = db.table("clientes").insert(datos).execute()
    return respuesta.data[0]


@router.get("/", response_model=List[ClienteResponse])
def obtener_clientes(db=Depends(get_db), _=Depends(obtener_usuario_actual)):
    """Cualquier miembro autenticado del staff puede consultar clientes."""
    # Nota la diferencia con la ruta de arriba: aquí solo exigimos
    # obtener_usuario_actual (o sea, "cualquiera con sesión iniciada,
    # sin importar el rol específico"), en vez de requiere_rol con una
    # lista concreta. Consultar la lista de clientes es algo que
    # prácticamente todos los roles del sistema necesitan poder hacer.
    respuesta = db.table("clientes").select("*").execute()
    return respuesta.data


@router.get("/{cliente_id}", response_model=ClienteResponse)
def obtener_cliente(cliente_id: int, db=Depends(get_db), _=Depends(obtener_usuario_actual)):
    # Ruta para consultar UN cliente puntual por su id (a diferencia de
    # la ruta anterior, que trae la lista completa).
    respuesta = db.table("clientes").select("*").eq("id", cliente_id).execute()
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return respuesta.data[0]
