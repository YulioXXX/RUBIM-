-- supabase_schema.sql
-- Ejecutar en el SQL Editor de tu proyecto Supabase.
-- Reemplaza cualquier tabla que hubieras creado a mano previamente si no coincide.

-- Tabla de personal / usuarios del sistema (antes se usaba sin estar definida en ningún lado)
create table if not exists usuarios (
    id bigint generated always as identity primary key,
    usuario text unique not null,
    contrasena text not null,              -- se guarda el HASH (bcrypt), nunca texto plano
    rol text not null,
    nombre_completo text,
    fecha_creacion timestamptz default now()
);

-- Proceso 1: Captación de Leads (NUEVO)
create table if not exists leads (
    id bigint generated always as identity primary key,
    nombre_prospecto text not null,
    telefono text not null,
    correo text,
    servicio_interes text not null,
    fecha_registro timestamptz default now(),
    convertido boolean default false
);

-- Almacén A1: Clientes
create table if not exists clientes (
    id bigint generated always as identity primary key,
    nombre text not null,
    tipo_cliente text not null,
    canal text not null,
    telefono text,
    estatus_expediente text default 'En revisión'
);

-- Almacén A2: Expedientes Contables / Transacciones
create table if not exists transacciones (
    id bigint generated always as identity primary key,
    cliente_id bigint references clientes(id),
    tipo_documento text not null,
    fecha_registro timestamptz default now(),
    procesado_por text,
    estado text default 'Pendiente'
);

-- Citas (integrado formalmente al sistema)
create table if not exists citas (
    id bigint generated always as identity primary key,
    cliente_id bigint references clientes(id),
    fecha_solicitud timestamptz not null,
    motivo text not null,
    confirmada boolean default false
);

-- Almacén A4: Facturas (Proceso 6 — NUEVO, no existía en absoluto)
create table if not exists facturas (
    id bigint generated always as identity primary key,
    cliente_id bigint references clientes(id),
    transaccion_id bigint references transacciones(id),
    numero_operacion text unique not null,
    servicio text not null,
    costo numeric(12,2) not null,
    fecha timestamptz default now()
);

-- Portal del Cliente (App Móvil): solicitudes de cuenta de acceso.
-- El cliente ya existe en "clientes" (fue capturado por Marketing/Secretaria);
-- esta tabla es la CAPA DE ACCESO DIGITAL a ese registro, separada a propósito.
create table if not exists cuentas_clientes (
    id bigint generated always as identity primary key,
    cliente_id bigint references clientes(id) not null,
    telefono text unique not null,
    correo text,
    contrasena text not null,           -- hash bcrypt, igual que en 'usuarios'
    estatus_solicitud text default 'Pendiente',  -- Pendiente | Aprobada | Rechazada
    motivo_rechazo text,
    fecha_solicitud timestamptz default now()
);
