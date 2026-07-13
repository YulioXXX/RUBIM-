# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import clientes, citas, transacciones, auth, leads, facturas, portal_cliente, cuentas_clientes

app = FastAPI(
    title="RUBIM API",
    description="API central en la nube para RUBIM, C.A. — TPS de gestión contable y fiscal.",
    version="1.1.0"
)

# CORS para desarrollo local.
#
# El frontend se abre con doble clic (file://...), lo cual hace que el
# navegador mande "Origin: null" en cada petición. Eso no calza con ninguna
# lista de orígenes específica, así que Starlette rechazaba el preflight con
# 400 "Disallowed CORS origin".
#
# La solución NO es volver a "allow_origins=['*'] + allow_credentials=True"
# (esa combinación es inválida y los navegadores la ignoran). En vez de eso:
# como el login no usa cookies de sesión — el token viaja en el header
# "Authorization", no en una cookie — es seguro poner allow_credentials=False
# y abrir el origen a todos. Si más adelante sirves el frontend desde un
# dominio real (producción), vuelve a restringir allow_origins a ese dominio
# exacto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rubimca.netlify.app",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(leads.router)
app.include_router(clientes.router)
app.include_router(citas.router)
app.include_router(transacciones.router)
app.include_router(facturas.router)
app.include_router(portal_cliente.router)
app.include_router(cuentas_clientes.router)


@app.get("/")
def read_root():
    return {"mensaje": "Servidor de RUBIM conectado a Supabase!", "estado": "Operativo"}
