-- Script para crear la base de datos de test
-- Este script debe ejecutarse como superusuario

-- Crear base de datos de test si no existe
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'petmarket_test') THEN
        CREATE DATABASE petmarket_test;
    END IF;
END
$$;

-- Grant privileges (aplicable después de crear la BD)
-- Esto se ejecuta en la BD creada
\c petmarket_test
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";