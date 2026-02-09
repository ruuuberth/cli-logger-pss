-- Script de inicialización para PostgreSQL
-- Crear base de datos y usuario si no existen

CREATE DATABASE IF NOT EXISTS pixelstarships;
CREATE USER IF NOT EXISTS pss_user WITH ENCRYPTED PASSWORD 'pss_password';
GRANT ALL PRIVILEGES ON DATABASE pixelstarships TO pss_user;

-- Conectar a la base de datos y crear extensiones
\c pixelstarships;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Confirmar creación
SELECT 'Database initialized successfully' as status;