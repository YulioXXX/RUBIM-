# ============================================================================
# database.py
#
# QUÉ HACE ESTE ARCHIVO, EN UNA FRASE:
# Abre y mantiene la conexión hacia Supabase (nuestra base de datos en la nube),
# para que el resto del sistema no tenga que reconectarse una y otra vez.

import os
# 'os' es una librería que viene incluida en Python. Nos deja leer información
# del sistema operativo — en este caso, la usamos para leer "variables de
# entorno", que son valores secretos guardados fuera del código (ver más abajo).

from dotenv import load_dotenv
# 'dotenv' es una librería externa (instalada con pip) que sabe leer el
# archivo ".env" — un archivo de texto plano donde guardamos contraseñas y
# claves secretas SEPARADAS del código fuente. Esto es una práctica de
# seguridad.

from supabase import create_client, Client
# Traemos del paquete oficial de Supabase dos cosas:
#   - create_client: una función que "abre la conexión" hacia Supabase.
#   - Client: el "tipo de dato" que representa esa conexión ya abierta
#     (lo usamos más abajo solo para indicar qué tipo de valor es 'supabase').

load_dotenv()
# Esta línea busca el archivo ".env" en la carpeta del proyecto y carga su
# contenido en la memoria del programa, como si fueran variables normales.
# Si no se llama a esta función, Python nunca se entera de que existe el
# archivo ".env" — por eso va de primero.

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Lee la variable llamada SUPABASE_URL desde el archivo .env (o desde el
# sistema operativo si se configuró de otra forma). Esta es la "dirección"
# de nuestro proyecto específico dentro de los servidores de Supabase —
# algo como una URL de página web, pero para la base de datos.

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Lo mismo, pero para la CLAVE de acceso. Esta clave es como una contraseña
# maestra: le dice a Supabase "sí, este programa tiene permiso de leer y
# escribir en esta base de datos". Por eso NUNCA debe escribirse directamente
# en el código ni compartirse en capturas de pantalla o en un grupo de chat.

if not SUPABASE_URL or not SUPABASE_KEY:
    # 'not' invierte un valor: si SUPABASE_URL está vacío o no existe,
    # 'not SUPABASE_URL' se vuelve verdadero. Lo mismo para la clave.
    # Este 'if' pregunta: "¿falta la URL O falta la clave?"
    raise RuntimeError(
        "Faltan SUPABASE_URL y/o SUPABASE_KEY. "
        "Copia .env.example a .env y coloca tus credenciales reales."
    )
    # 'raise' detiene el programa por completo y muestra este mensaje de
    # error. Es intencional: preferimos que el sistema NO arranque a que
    # arranque a medias y falle de forma confusa más adelante. Es una
    # protección para que, si alguien clona el proyecto y se le olvida
    # crear su archivo .env, entienda inmediatamente qué le falta.

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# AQUÍ es donde realmente se abre la conexión. create_client() recibe la
# URL y la clave, y devuelve un objeto (lo llamamos 'supabase') que
# representa esa conexión ya lista para usarse. A partir de aquí, cualquier
# parte del código que tenga esta variable puede pedirle datos a la base
# de datos (por ejemplo: "tráeme todos los clientes").
# El ": Client" después del nombre es solo una anotación de tipo — le dice
# a quien lea el código (y a herramientas de autocompletado) qué clase de
# objeto es 'supabase'. No cambia cómo funciona el programa.


def get_db():
    # Esto es una FUNCIÓN — un bloque de código con un nombre, que se puede
    # "llamar" (ejecutar) desde otras partes del programa cuantas veces se
    # necesite, sin tener que copiar y pegar el código de conexión cada vez.
    return supabase
    # 'return' hace que la función entregue este valor a quien la llamó.
    # En este caso, entrega la conexión que ya abrimos arriba.
    #
    # ¿PARA QUÉ SIRVE ESTO SI YA TENEMOS 'supabase' ARRIBA?
    # Porque en FastAPI (el framework que usamos para las rutas/endpoints),
    # las funciones como esta se usan como "dependencias": cada ruta del
    # sistema simplemente escribe "db = Depends(get_db)" y FastAPI se
    # encarga de llamarla y entregarle el resultado automáticamente.
    # Es un patrón de diseño llamado "inyección de dependencias" — permite
    # cambiar CÓMO nos conectamos a la base de datos en un solo lugar
    # (aquí) sin tener que tocar los más de 6 archivos que la usan.
