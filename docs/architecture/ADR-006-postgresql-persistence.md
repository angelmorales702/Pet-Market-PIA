# ADR-006: Persistencia en PostgreSQL con SQLAlchemy 2 y Alembic

## Estatus
Aprobado

## Contexto
Se requiere almacenamiento relacional persistente, compatible con transacciones ACID, soporte para entornos Dockerizados y plataformas de nube (Render / Fly.io / Railway).

## Decisión
1. Utilizar **PostgreSQL 16** como base de datos relacional.
2. Emplear **SQLAlchemy 2.0** en modo async/sync con Mappers ou Repository pattern en `src/infrastructure/db/` para aislar los modelos de dominio de las tablas SQL.
3. Utilizar **Alembic** para la gestión de migraciones de base de datos de manera versionada.

## Consecuencias
- **Positivas**:
  - Garantías ACID en transacciones de checkout y actualización de stocks.
  - Portabilidad total en contenedores Docker e integración CI/CD.
- **Negativas**:
  - Gestión explícita de migraciones en cada cambio de esquema.

## Detalles de Implementación

### Columnas `estado` como String con Validación en el Dominio

Las columnas `estado` en las tablas `pedidos`, `surtidos`, `pagos`, `envios` y `devoluciones` se definen como `String(50)` en PostgreSQL, **no como tipos ENUM**.

**Razón**: 
- PostgreSQL crea tipos de enum explícitos que pueden causar conflictos durante migraciones o al usar múltiples esquemas.
- SQLAlchemy 2.0 con `SQLEnum` puede generar tipos duplicados si la migración se ejecuta múltiples veces.
- El dominio tiene sus propios tipos de enum (en `src/domain/value_objects.py`) que validan legalmente los estados.

**Patrón**:
- El dominio define enums como `EstadoPedido`, `EstadoSurtido`, `EstadoPago`, `EstadoEnvio`, `EstadoDevolucion`.
- Estos enums tienen validación explícita en el código de dominio.
- La base de datos almacena los valores como `String(50)` con validación en el dominio.
- Las migraciones usan `sa.String(length=50)` con `server_default` para valores por defecto.

**Validación**: Cualquier valor inválido en la columna `estado` será rechazado por la lógica del dominio al deserializar el agregado.

### Foreign Keys entre Aggregate Roots

Según ADR-002 y ADR-003, las relaciones entre **aggregate roots distintos** deben referenciar solo por identificador (ID), **sin ForeignKey**.

**Regla aplicada**:
- `Existencia.almacen_id`: tiene FK → `almacenes.id` (misma agregación: Almacén)
- `Existencia.producto_id`: **NO tiene FK** → `productos.id` (aggregate root distinto)
- `Pedido.cliente_id`: **NO tiene FK** → `clientes.id` (aggregate root distinto)
- `Surtido.almacen_id`: **NO tiene FK** → `almacenes.id` (aggregate root distinto; Surtido es entidad de Pedido)
