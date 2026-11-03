-- Script de inicialización para bases de datos
-- Crea la base de datos de test si no existe

-- Nota: PostgreSQL crea automáticamente las bases de datos especificadas en POSTGRES_DB
-- Este archivo puede ser usado para crear tablas o extensiones adicionales

-- Ejemplo: Crear extensión para UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";