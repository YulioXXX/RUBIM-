# RUBIM — Backend refactorizado

## Qué cambió y por qué

### Eliminado
- **`models.py`**: definía modelos SQLAlchemy que ningún router usaba realmente
  (todos hablan directo con Supabase vía `db.table(...)`). Era código muerto que
  solo generaba confusión sobre qué motor de datos se está usando.
- **`rubim.db`**: archivo SQLite vacío (0 tablas), residuo de un intento anterior
  con SQLAlchemy que quedó huérfano al migrar a Supabase.
- Si en algún momento quieres SQLAlchemy como capa real (por ejemplo para
  correr consultas complejas o para desacoplarte de Supabase), lo reconstruimos
  con un `engine` y `Session` de verdad, conectados a los routers.

### Seguridad (antes no existía ninguna)
- Contraseñas ahora se guardan con **hash bcrypt** (`security.py`), nunca en texto plano.
- Login devuelve un **JWT con expiración** (`JWT_EXPIRE_MINUTES` en `.env`).
- Todas las rutas de negocio ahora requieren un token válido (`obtener_usuario_actual`),
  y las rutas sensibles requieren además el **rol correcto** (`requiere_rol(...)`),
  verificado en el backend — antes la verificación de rol vivía solo en `localStorage`
  del navegador y era trivial de saltarse.
- Credenciales de Supabase movidas de `database.py` a un archivo `.env` (no se sube a git).
- CORS restringido a orígenes reales en vez de `*` combinado con `allow_credentials=True`.

### Bug de compatibilidad corregido
- El patrón `data, count = db.table(...).insert(...).execute()` es de una versión
  antigua de `supabase-py`/`postgrest-py`. Con el cliente actual (`supabase==2.10.0`,
  agregado a `requirements.txt` — antes faltaba por completo) esa forma de
  desempacar falla. Ahora todos los routers usan `respuesta = ...execute()` y
  leen `respuesta.data`.

### Nuevo: Proceso 1 — Captación de Leads (`routers/leads.py`)
Antes el sistema iba directo a "Cliente" completo. Ahora existe la etapa de
lead (flujos 1-4 del DFD) con conversión formal a cliente (flujos 5-7), y la
asignación de **canal** (Altos/Bajos) ahora la calcula el backend — antes
dependía de un `<input readonly>` en el frontend, editable desde las
herramientas de desarrollador.

### Nuevo: Proceso 6 — Facturación (`routers/facturas.py`)
No existía absolutamente nada de esto en el código, aunque el documento y el
diagrama de clases sí contemplan `Factura` y el almacén A4. Incluye validación
de que solo se facture un trámite ya `Completado`.

### Citas — integrado formalmente
Por tu decisión, Citas queda como parte oficial del sistema, a cargo de
Secretaria. **Pendiente de tu lado**: reflejarlo también en el DFD (como
sub-flujo del Proceso 2/5 con un almacén "A5 Citas") y en el diagrama de
clases, para que el documento y el código queden 100% alineados.

### Roles del sistema, alineados con el organigrama/DFD
`Administrador, Asesor de Marketing, Secretaria, Contador Auxiliar,
Contador Junior, Contador Senior, Contador Gerente, Asesor Financiero`

## Cómo levantarlo

```bash
pip install -r requirements.txt
cp .env.example .env        # y coloca tus credenciales reales
```

1. Ejecuta `supabase_schema.sql` en el SQL Editor de tu proyecto Supabase.
2. Crea tu primer usuario Administrador **directamente en Supabase** (Table
   Editor → usuarios), con la contraseña ya hasheada. Puedes generarla así:
   ```bash
   python -c "from security import hash_password; print(hash_password('tu_password'))"
   ```
   (Es la única vez que hace falta hacerlo a mano — de ahí en adelante, un
   Administrador ya logueado puede crear al resto del personal desde `/auth/registrar`.)
3. `uvicorn main:app --reload`

## Próximo paso
Backend listo — cuando quieras seguimos con el frontend (login.html, index.html,
app.js) para que hable con estos endpoints nuevos (tokens en el header
Authorization, módulo de Leads, módulo de Facturas, y los roles nuevos en el
formulario de "Crear Acceso").
