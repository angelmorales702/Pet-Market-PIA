# CLAUDE.md - PetMarket Project Guidelines

## Project Context
PetMarket es un sistema de e-commerce para productos de mascotas implementado con Clean Architecture + DDD.

## Technical Stack
- **PostgreSQL 16** con SQLAlchemy 2.0 (Declarative)
- **Python 3.11+** con FastAPI
- **Alembic** para migraciones
- **Docker** para despliegue

## Arquitectura y Reglas

### Foreign Keys entre Aggregates
Según ADR-002 y ADR-003, las relaciones entre **aggregate roots distintos** deben referenciar solo por identificador (UUID), **sin ForeignKey** en la base de datos:
- `Existencia.producto_id`: NO tiene FK (producto es aggregate root distinto)
- `Pedido.cliente_id`: NO tiene FK (cliente es aggregate root distinto)
- `Surtido.almacen_id`: NO tiene FK (almacen es aggregate root distinto; surtido es entidad de pedido)

### Columnas `estado` como String
Las columnas `estado` se definen como `String(50)`, **no como ENUM**:
- `EstadoPedido`, `EstadoSurtido`, `EstadoPago`, `EstadoEnvio`, `EstadoDevolucion`
- El dominio tiene sus propios tipos de enum que validan legalmente los estados
- La base de datos almacena los valores como String con validación en el dominio

### Value Objects
- **Sku**: Formato "SKU-XXXXX" con guion (ej: "SKU-00001")
- **Dinero**: cantidad + moneda
- **Guia**: formato "GUIA-ENVIO-XXXXX"
- **MotivoDevolucion**: texto validado

### SKU Validation
SKUs deben seguir el formato `SKU-XXXXX` (5 dígitos después del guion):
- Válido: `SKU-00001`, `SKU-12345`
- Inválido: `SKU00001`, `SKU-PAGO-001` (tiene guiones extra)

## Testing Rules
- Usar PostgreSQL real via Docker para tests de infraestructura
- Tests requieren variable `TEST_DATABASE_URL`
- Para CI: `REQUIRE_DB=1` hace fallar los tests si la DB no está disponible
- Cobertura mínima: **80%**
- Ejecutar: `pytest tests/ --cov=src --cov-fail-under=80`

## Git Workflow
- Commits firmados con: `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- PRs con: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`

## Docker
- Usar base de datos `petmarket_test` para tests de integración
- El docker-compose.yml incluye:
  - `name: petmarket` (nombre del proyecto)
  - `healthcheck` para servicios
  - Volumen persistente `postgres_data`

## Comandos Útiles
```bash
# Iniciar servicios
docker compose up -d db

# Ejecutar tests con cobertura
pytest tests/ --cov=src --cov-fail-under=80

# Migraciones
alembic revision --autogenerate -m "mensaje"
alembic upgrade head
```