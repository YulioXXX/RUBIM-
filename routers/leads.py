# ============================================================================
# routers/leads.py
#
# QUÉ HACE ESTE ARCHIVO, EN UNA FRASE:
# Maneja el Proceso 1 del DFD ("Captación de Leads"): guarda los datos de
# un prospecto que todavía no es cliente formal, y permite convertirlo en
# Cliente real cuando la Secretaria (o Marketing) decide formalizarlo.
#
# Un "lead" es simplemente un prospecto: alguien que mostró interés pero
# aún no llenó el registro completo como cliente de la firma.
# ============================================================================
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
# 'datetime' para registrar la fecha/hora exacta en que se capturó el
# lead. 'timezone' asegura que esa fecha quede en UTC (un estándar
# internacional), para que no haya ambigüedad de husos horarios.

from database import get_db
from schemas import LeadCreate, LeadResponse, ClienteResponse
from security import requiere_rol

router = APIRouter(
    prefix="/leads",
    tags=["Captación de Leads (Proceso 1)"]
)


def _asignar_canal(tipo_cliente: str) -> str:
    """
    Regla de negocio del DFD (flujo 5-7): Industriales y Comerciantes van a
    Canales Altos, Particulares a Canales Bajos.

    Antes esta regla vivía SOLO en app.js (frontend). Cualquiera podía abrir
    las herramientas de desarrollador, cambiar el valor del <input readonly>
    o llamar la API directamente con un canal arbitrario. Ahora el backend
    la recalcula siempre, sin confiar en lo que mande el cliente.
    """
    # Esta es una función auxiliar (el guion bajo al inicio indica que es
    # de uso interno de este archivo). Recibe el tipo de cliente como
    # texto y devuelve a qué "canal" de atención pertenece.

    if tipo_cliente in ("Industriales", "Comerciantes"):
        # "in (...)" pregunta: "¿tipo_cliente es igual a alguno de estos
        # dos valores?" — más corto que escribir dos "or" seguidos.
        return "Canales Altos"
    return "Canales Bajos"
    # Si no era Industriales ni Comerciantes, por descarte cae en
    # Canales Bajos (que en la práctica corresponde a "Particulares").


@router.post("/", response_model=LeadResponse)
def capturar_lead(lead: LeadCreate, db=Depends(get_db)):
    """
    Flujo (1): el prospecto (Cliente en el DFD, antes de formalizarse) envía
    sus datos de contacto e interés. Ruta pública a propósito: en el DFD este
    flujo viene desde afuera del sistema, antes de que exista cualquier cuenta.
    """
    # OJO: esta ruta NO tiene "dependencies=[Depends(requiere_rol(...))]",
    # es decir, no exige ningún token. Es una decisión intencional: en el
    # DFD, este flujo representa a un prospecto que AÚN NO es cliente ni
    # tiene cuenta — pedirle un login no tendría sentido en este punto
    # del proceso real de negocio.

    datos = lead.model_dump()
    # Convierte el objeto validado (LeadCreate) en un diccionario normal
    # de Python, listo para mandarlo a Supabase.

    datos["fecha_registro"] = datetime.now(timezone.utc).isoformat()
    # Agregamos manualmente la fecha/hora actual (en UTC), convertida a
    # texto con formato estándar (.isoformat()) porque así es como
    # Supabase espera recibir fechas en un insert.

    datos["convertido"] = False
    # Todo lead nace como "no convertido" — todavía no es cliente.

    respuesta = db.table("leads").insert(datos).execute()
    # Inserta la nueva fila en la tabla "leads" de Supabase.

    return respuesta.data[0]
    # Supabase devuelve, dentro de respuesta.data, la fila que se acaba
    # de insertar (incluyendo el "id" que la base de datos le asignó
    # automáticamente). Tomamos el primer (y único) elemento de esa lista.


@router.get("/", response_model=List[LeadResponse])
def listar_leads(db=Depends(get_db), _=Depends(requiere_rol("Asesor de Marketing", "Administrador"))):
    # Fíjate en "_=Depends(...)": usamos guion bajo como nombre de
    # variable porque NO vamos a usar ese resultado dentro de la función
    # — solo nos interesa que requiere_rol() se ejecute y, si el rol no
    # calza, rechace la petición antes de llegar aquí. Es una convención
    # común en Python para "esta variable existe pero no me importa
    # guardarla con un nombre descriptivo".
    respuesta = db.table("leads").select("*").order("fecha_registro", desc=True).execute()
    # "order(..., desc=True)" ordena los resultados del más reciente al
    # más antiguo (orden descendente por fecha de registro).
    return respuesta.data


@router.post("/{lead_id}/convertir", response_model=ClienteResponse)
# "{lead_id}" dentro de la ruta es un "parámetro de ruta" — una parte
# variable de la URL. Por ejemplo, si alguien llama a
# "/leads/7/convertir", FastAPI automáticamente toma el número 7 y se lo
# pasa a nuestra función como el argumento "lead_id" de abajo.
def convertir_lead_a_cliente(
    lead_id: int,
    tipo_cliente: str,
    # 'tipo_cliente' aquí NO viene de la URL como parámetro de ruta (no
    # está entre llaves {} arriba), así que FastAPI lo busca como
    # "query parameter" — la parte de la URL después del "?", por
    # ejemplo: "/leads/7/convertir?tipo_cliente=Particulares".
    db=Depends(get_db),
    _=Depends(requiere_rol("Secretaria", "Asesor de Marketing", "Administrador")),
):
    """
    Flujo (5)-(7): la Secretaria formaliza al prospecto como Cliente y le
    asigna canal. Corresponde al Proceso 2 del DFD.
    """
    lead_res = db.table("leads").select("*").eq("id", lead_id).execute()
    # Buscamos el lead específico por su id.

    if not lead_res.data:
        raise HTTPException(status_code=404, detail="Lead no encontrado.")
        # 404 = "Not Found" — el código estándar para "lo que pediste no existe".

    lead = lead_res.data[0]

    if lead["convertido"]:
        # Si este lead YA se había convertido antes, no dejamos que se
        # convierta dos veces (evitamos clientes duplicados por error).
        raise HTTPException(status_code=409, detail="Este lead ya fue convertido en cliente.")

    canal = _asignar_canal(tipo_cliente)
    # Aquí es donde se aplica la regla de negocio real: el canal NO lo
    # decide el frontend, lo calcula esta función del backend.

    nuevo_cliente = {
        "nombre": lead["nombre_prospecto"],
        "tipo_cliente": tipo_cliente,
        "canal": canal,
        "telefono": lead["telefono"],
        "estatus_expediente": "En revisión",
    }
    # Armamos el diccionario con los datos del nuevo cliente, tomando la
    # información que ya teníamos guardada del lead original (nombre,
    # teléfono) y agregando lo nuevo (tipo_cliente que se decidió al
    # convertir, canal calculado, y un estatus inicial).

    cliente_creado = db.table("clientes").insert(nuevo_cliente).execute()
    # Se crea el cliente formal en la tabla "clientes".

    db.table("leads").update({"convertido": True}).eq("id", lead_id).execute()
    # Y marcamos el lead original como "ya convertido", para que no
    # vuelva a aparecer en la lista de prospectos pendientes ni se pueda
    # convertir de nuevo por error.

    return cliente_creado.data[0]
    # Devolvemos el cliente recién creado (con su id ya asignado).
