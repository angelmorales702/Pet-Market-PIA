-- Script de inicialización para bases de datos PostgreSQL
-- Se ejecuta automáticamente cuando se crea el volumen

-- Extensión para UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Crear base de datos de test (para CI/CD y testing)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'petmarket_test') THEN
        CREATE DATABASE petmarket_test;
    END IF;
END
$$;

-- Conceder privilegios en la base de test
-- (se ejecuta como postgres user)