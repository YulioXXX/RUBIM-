# ============================================================================
# routers/facturas.py
#
# QUÉ HACE ESTE ARCHIVO, EN UNA FRASE:
# Genera y consulta facturas — el Proceso 6 del DFD ("Facturación de
# Servicios") y el almacén A4. Incluye una regla de negocio real: no se
# puede facturar un trámite que todavía no está Completado.
# ============================================================================
import random
import string
# Dos librerías incluidas en Python:
#   - random: para generar valores aleatorios.
#   - string: nos da listas de caracteres ya armadas (como todos los
#     dígitos del 0 al 9), para no tener que escribirlas a mano.

from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from database import get_db
from schemas import FacturaCreate, FacturaResponse
from security import requiere_rol, obtener_usuario_actual

router = APIRouter(
    prefix="/facturas",
    tags=["Facturación de Servicios (Proceso 6, almacén A4)"]
)


def _generar_numero_operacion() -> str:
    sufijo = "".join(random.choices(string.digits, k=8))
    # random.choices(string.digits, k=8) elige 8 caracteres al azar,
    # CON reemplazo (el mismo dígito puede repetirse), de la lista de
    # todos los dígitos ("0123456789"). El resultado es una LISTA de 8
    # caracteres, por ejemplo ['3','9','0','0','1','4','7','2'].
    # "".join(...) los pega todos juntos en un solo texto: "39001472".
    return f"RUBIM-{sufijo}"
    # f"RUBIM-{sufijo}" es un "f-string" — una forma de Python de
    # insertar el valor de una variable dentro de un texto. El resultado
    # final es algo como "RUBIM-39001472".


@router.post("/", response_model=FacturaResponse, dependencies=[
    Depends(requiere_rol("Asesor Financiero", "Administrador"))
])
def generar_factura(factura: FacturaCreate, db=Depends(get_db)):
    """
    Flujo (16)-(26) del DFD: una vez que Proceso 4 marca un trámite como
    Completado, el Asesor Financiero genera el cobro y lo guarda en A4.
    """
    # Si viene ligada a un trámite, validamos que ese trámite exista y esté completado
    if factura.transaccion_id is not None:
        # La factura puede o no estar ligada a un expediente específico
        # (transaccion_id es opcional, ver schemas.py). Si SÍ viene,
        # hacemos una validación extra antes de aceptar la factura:

        trans = db.table("transacciones").select("estado").eq("id", factura.transaccion_id).execute()
        # Consultamos SOLO la columna "estado" de ese trámite (no
        # necesitamos traer todas las columnas, así que optimizamos la
        # consulta pidiendo solo lo que vamos a usar).

        if not trans.data:
            raise HTTPException(status_code=404, detail="El trámite/transacción indicado no existe.")

        if trans.data[0]["estado"] != "Completado":
            # AQUÍ está la regla de negocio real, no solo un CRUD: no
            # dejamos generar una factura si el trabajo contable
            # asociado todavía no se terminó de revisar.
            raise HTTPException(
                status_code=409,
                detail="No se puede facturar un trámite que aún no está Completado."
            )

    datos = factura.model_dump()
    datos["numero_operacion"] = _generar_numero_operacion()
    # Generamos un número de operación único para identificar esta
    # factura (como el número de referencia de un pago).

    datos["fecha"] = datetime.now(timezone.utc).isoformat()

    respuesta = db.table("facturas").insert(datos).execute()
    return respuesta.data[0]


@router.get("/", response_model=List[FacturaResponse])
def listar_facturas(db=Depends(get_db), _=Depends(obtener_usuario_actual)):
    # Cualquier empleado autenticado puede ver la lista completa de
    # facturas emitidas (por ejemplo, para efectos de auditoría interna).
    respuesta = db.table("facturas").select("*").execute()
    return respuesta.data


@router.get("/cliente/{cliente_id}", response_model=List[FacturaResponse])
def facturas_de_cliente(cliente_id: int, db=Depends(get_db), _=Depends(obtener_usuario_actual)):
    """Corresponde al flujo (25): entregar la factura al cliente al consultarla."""
    respuesta = db.table("facturas").select("*").eq("cliente_id", cliente_id).execute()
    return respuesta.data
