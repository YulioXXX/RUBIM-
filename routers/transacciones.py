# ============================================================================
# routers/transacciones.py
#
# QUÉ HACE ESTE ARCHIVO, EN UNA FRASE:
# Maneja el expediente contable de cada cliente: registrar los documentos
# que entrega (Proceso 3, Contador Auxiliar) y hacerles seguimiento hasta
# que un Contador con más jerarquía los marca como Completados (Proceso 4).
# Corresponde al almacén A2 "Expedientes Contables" del DFD.
# ============================================================================
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from database import get_db
from schemas import TransaccionCreate, TransaccionResponse
from security import requiere_rol, obtener_usuario_actual

router = APIRouter(
    prefix="/transacciones",
    tags=["Expedientes Contables (Proceso 3/4, almacén A2)"]
)


@router.post("/", response_model=TransaccionResponse, dependencies=[
    Depends(requiere_rol("Contador Auxiliar", "Contador Junior", "Contador Senior", "Contador Gerente", "Administrador"))
])
# Fíjate que aquí metimos los CUATRO niveles de Contador dentro de la
# misma lista de roles permitidos — cualquiera de ellos puede registrar
# un documento nuevo, porque en la práctica el primer contacto con el
# expediente lo puede iniciar cualquier nivel del área contable.
def registrar_transaccion(transaccion: TransaccionCreate, db=Depends(get_db)):
    datos = transaccion.model_dump()
    datos["fecha_registro"] = datetime.now(timezone.utc).isoformat()
    # Igual que en leads.py: registramos la fecha/hora exacta del
    # servidor, en vez de confiar en una fecha que mande el navegador
    # (que podría estar mal configurado o manipulado).

    # Fix del mismo bug de unpacking de execute() que en clientes.py/citas.py
    respuesta = db.table("transacciones").insert(datos).execute()
    return respuesta.data[0]


@router.get("/", response_model=List[TransaccionResponse])
def obtener_transacciones(db=Depends(get_db), _=Depends(obtener_usuario_actual)):
    # Trae TODOS los expedientes registrados, sin filtrar por cliente.
    # Útil para una vista general de "todo lo que hay pendiente".
    respuesta = db.table("transacciones").select("*").execute()
    return respuesta.data


@router.get("/cliente/{cliente_id}", response_model=List[TransaccionResponse])
def obtener_transacciones_de_cliente(cliente_id: int, db=Depends(get_db), _=Depends(obtener_usuario_actual)):
    """
    Corresponde al Proceso 5 (Consultar y entregar documentos, Secretaria):
    permite ver el expediente contable completo de un cliente puntual.
    Esta consulta no existía en el sistema original.
    """
    # A diferencia de la ruta anterior, esta SÍ filtra: solo trae los
    # documentos de UN cliente en específico (el que viene en la URL).
    respuesta = db.table("transacciones").select("*").eq("cliente_id", cliente_id).execute()
    return respuesta.data


@router.patch("/{transaccion_id}/estado", response_model=TransaccionResponse, dependencies=[
    Depends(requiere_rol("Contador Junior", "Contador Senior", "Contador Gerente", "Administrador"))
])
# OJO: en esta ruta específica, "Contador Auxiliar" NO está en la lista
# de roles permitidos — a propósito. La idea de negocio es que el
# Auxiliar puede RECIBIR y registrar documentos (ruta de arriba), pero
# el AVANCE de estado (que implica revisión/validación contable) debe
# hacerlo un Contador de mayor jerarquía.
def actualizar_estado_transaccion(transaccion_id: int, nuevo_estado: str, db=Depends(get_db)):
    if nuevo_estado not in ("Pendiente", "En revisión", "Completado"):
        # Verificación extra de seguridad: aunque 'nuevo_estado' llega
        # como texto libre (query parameter), no dejamos que se guarde
        # cualquier valor — solo estos tres exactos.
        raise HTTPException(status_code=400, detail="Estado inválido.")
        # 400 = "Bad Request" — la petición está mal formada/con datos
        # inválidos, antes de siquiera intentar nada en la base de datos.

    respuesta = db.table("transacciones").update({"estado": nuevo_estado}).eq("id", transaccion_id).execute()
    if not respuesta.data:
        raise HTTPException(status_code=404, detail="Transacción no encontrada.")
    return respuesta.data[0]
