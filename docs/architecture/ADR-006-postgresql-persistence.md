# ADR-006: Persistencia en PostgreSQL con SQLAlchemy 2 y Alembic

## Estatus
Aprobado

## Contexto
Se requiere almacenamiento relacional persistente, compatible con transacciones ACID, soporte para entornos Dockerizados y plataformas de nube (Render / Fly.io / Railway).

## Decisión
1. Utilizar **PostgreSQL 16** como base de datos relacional.
2. Emplear **SQLAlchemy 2.0** en modo async/sync con Mappers o Repository pattern en `src/infrastructure/db/` para aislar los modelos de dominio de las tablas SQL.
3. Utilizar **Alembic** para la gestión de migraciones de base de datos de manera versionada.

## Consecuencias
- **Positivas**:
  - Garantías ACID en transacciones de checkout y actualización de stocks.
  - Portabilidad total en contenedores Docker e integración CI/CD.
- **Negativas**:
  - Gestión explícita de migraciones en cada cambio de esquema.
