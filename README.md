# PetMarket - Sistema de E-commerce para Mascotas

Sistema de e-commerce implementado con **Clean Architecture + DDD**, PostgreSQL, SQLAlchemy 2.0 y FastAPI.

## Enlaces

| Recurso | URL |
|---|---|
| Repositorio | https://github.com/angelmorales702/Pet-Market-PIA |
| API desplegada (Render) | https://pet-market-pia.onrender.com |
| Swagger UI / OpenAPI | https://pet-market-pia.onrender.com/docs |
| Health check | https://pet-market-pia.onrender.com/health |

> **Nota:** el despliegue usa el plan gratuito de Render, por lo que el servicio se suspende tras un periodo de inactividad. La primera petición puede tardar hasta ~1 minuto en responder.

## Tecnologías

- **Python 3.11+** con FastAPI
- **PostgreSQL 16** con SQLAlchemy 2.0 (Declarative)
- **Alembic** para migraciones
- **Docker / Docker Compose** para contenerización
- **GitHub Actions** para CI/CD
- **Render** para el despliegue
- **State Machine Pattern** para transiciones de estado de dominio

## Arquitectura

El proyecto sigue los principios de Clean Architecture y Domain-Driven Design (DDD):

- **Dominio** (`src/domain`): Aggregates (Pedido, Cliente, Producto, Almacen, Pago, Envio, Devolucion), Entities, Value Objects y State Machine
- **Aplicación** (`src/application`): Ports, Adapters, Use Cases
- **Infraestructura** (`src/infrastructure`): SQLAlchemy 2.0, Alembic, Repositorios
- **API** (`src/api`): Controllers / endpoints REST con FastAPI

### ADR Principales

- **ADR-002/003**: No ForeignKey constraints entre aggregates distintos (referencian solo por ID)
- **ADR-006**: Columnas `estado` como String(50), validación en el dominio

## Documentación

| Documento | Ubicación |
|---|---|
| BRD | `docs/BRD.md` |
| Arquitectura, diagramas y ADRs | `docs/architecture/` |
| Especificación OpenAPI | `docs/api/openapi.json` |

La trazabilidad entre análisis e implementación se muestra en la tabla de endpoints (columna *User Story*), que enlaza cada caso de uso con las historias de usuario del BRD.

## Requisitos

- Python 3.11+
- PostgreSQL 16
- Docker y Docker Compose

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/angelmorales702/Pet-Market-PIA.git
cd Pet-Market-PIA
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate  # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores
```

## Desarrollo

### Iniciar servicios

```bash
docker compose up -d db
```

### Ejecutar migraciones

```bash
alembic upgrade head
```

### Poblar datos semilla

```bash
python scripts/seed_data.py
```

### Arrancar la API

```bash
python -m uvicorn src.api.main:app --reload --port 8000
```

### Documentación interactiva

Una vez arrancada la API, visita:

- **Swagger/OpenAPI**: http://localhost:8000/docs
- **Redoc**: http://localhost:8000/redoc

### Health Check

```bash
curl http://localhost:8000/health
# Respuesta: {"status": "healthy", "service": "petmarket-api"}
```

## Endpoints

| Endpoint                                 | Método | Descripción                      | User Story     |
|------------------------------------------|--------|----------------------------------|----------------|
| `/health`                                | GET    | Health check                     | -              |
| `/productos`                             | GET    | Listar productos del catálogo    | US-001         |
| `/productos/{sku}`                       | GET    | Detalles de un producto          | US-001         |
| `/almacenes`                             | GET    | Listar almacenes                 | -              |
| `/almacenes/{id}/inventario`             | GET    | Inventario de un almacén         | US-001         |
| `/pedidos`                               | POST   | Crear pedido (checkout)          | US-004         |
| `/pedidos/{id}`                          | GET    | Consultar estado de pedido       | US-012         |
| `/clientes/{id}/pedidos`                 | GET    | Listar pedidos de cliente        | US-012         |
| `/pedidos/{id}/cancelar`                 | POST   | Cancelar pedido                  | US-008, US-009 |
| `/pedidos/{id}/iniciar-preparacion`      | POST   | Iniciar preparación              | US-007         |
| `/pedidos/{id}/confirmar-empaque`        | POST   | Confirmar empaquetado            | US-007         |
| `/pedidos/{id}/enviar`                   | POST   | Despachar con guía               | US-006         |
| `/pedidos/{id}/entrega`                  | POST   | Registrar entrega                | US-010, US-011 |
| `/pagos`                                 | POST   | Procesar pago                    | US-003, US-004 |
| `/devoluciones`                          | POST   | Solicitar devolución             | US-013, US-014 |
| `/devoluciones/{id}/autorizar`           | POST   | Autorizar devolución             | US-014         |
| `/devoluciones/{id}/rechazar`            | POST   | Rechazar devolución              | US-014         |
| `/devoluciones/{id}/confirmar-recepcion` | POST   | Confirmar recepción almacén      | US-014, US-015 |
| `/almacenes/{id}/discrepancia`           | POST   | Detectar discrepancia inventario | US-016         |

## Pruebas

### Ejecutar tests

```bash
# Tests con PostgreSQL local (exige cobertura mínima del 80%)
REQUIRE_DB=1 pytest tests/ --cov=src --cov-fail-under=80
```

### Ejecutar tests con Docker Compose

```bash
# Levantar la base de datos
docker compose up -d db

# Ejecutar tests contra base de test propia
docker compose --profile tests run --rm tests
```

### Tests de integración API

```bash
python -m pytest tests/test_api.py -v
```

## CI/CD

El pipeline de GitHub Actions (`.github/workflows/`) ejecuta las pruebas con el umbral de cobertura del 80% en cada push. El estado se consulta en la pestaña **Actions** del repositorio.

## Migraciones

```bash
# Crear nueva migración
alembic revision --autogenerate -m "descriptivo mensaje"

# Aplicar migraciones
alembic upgrade head

# Revertir
alembic downgrade -1
```

## Exportar OpenAPI

```bash
python scripts/export_openapi.py
# Genera docs/api/openapi.json
```

## Variables de Entorno

| Variable                        | Descripción                      | Valor por defecto                                                          |
|---------------------------------|----------------------------------|----------------------------------------------------------------------------|
| `DATABASE_URL`                  | URL de conexión PostgreSQL       | `postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db`   |
| `TEST_DATABASE_URL`             | URL para tests                   | `postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_test` |
| `CORS_ORIGINS`                  | Orígenes permitidos CORS         | `*`                                                                        |
| `PORT`                          | Puerto de la API                 | `8000`                                                                     |
| `ENVIRONMENT`                   | Entorno (development/production) | `development`                                                              |
| `MAX_INTENTOS_ENTREGA`          | Máximo intentos entrega          | `3`                                                                        |
| `PLAZO_CANCELACION_DIAS`        | Plazo cancelación en días        | `2`                                                                        |
| `ESTRATEGIA_ASIGNACION_ALMACEN` | Estrategia asignación almacén    | `MENOR_NUMERO_ALMACENES`                                                   |

Ver `.env.example` para configuración completa. Los valores de producción se configuran como variables de entorno en Render; no se suben secretos al repositorio.

## Despliegue

### Docker (local)

```bash
docker compose build
docker compose up -d app db
```

### Despliegue en Render

El despliegue se describe en `render.yaml` (Render Blueprint) y usa el `Dockerfile` del proyecto.

1. En Render: **New + → Blueprint** y seleccionar este repositorio.
2. Render crea el servicio web (`petmarket-api`) y la base PostgreSQL (`petmarket-db`).
3. `DATABASE_URL` se inyecta automáticamente desde la base de datos (`fromDatabase`).
4. Al arrancar, el contenedor ejecuta `alembic upgrade head` y luego inicia `uvicorn` en el puerto definido por `PORT`.
5. Render valida el servicio con el health check `GET /health`.

### Datos semilla en producción

Render no ofrece shell en el plan gratuito, por lo que el seed se ejecuta una sola vez desde una máquina local, apuntando a la base de Render con su *External Database URL* (Render → base de datos → Connect → External):

```bash
# Linux / Mac / Git Bash
DATABASE_URL="<external-database-url>?sslmode=require" python scripts/seed_data.py

# Windows PowerShell
$env:DATABASE_URL="<external-database-url>?sslmode=require"; python scripts/seed_data.py
```

El script usa operaciones *upsert*, por lo que puede ejecutarse más de una vez sin duplicar datos.

## Demostración rápida

1. Abrir https://pet-market-pia.onrender.com/docs
2. `GET /productos` para ver el catálogo (10 productos de ejemplo).
3. `POST /pedidos` (con el header `X-Cliente-Id` de un cliente del seed) para crear un pedido.
4. `POST /pagos`, y luego `/pedidos/{id}/iniciar-preparacion`, `confirmar-empaque`, `enviar` y `entrega` para recorrer la máquina de estados.
5. `GET /pedidos/{id}` para consultar el estado actual.

## Limitaciones Conocidas

- Sin autenticación real: `X-Cliente-Id` como supuesto
- Autorización de Atención al cliente por bandera en petición
- Pasarela de pago simulada (sin integración real)
- Sin rate limiting ni logging estructurado
- Sin monitoreo ni métricas de producción
- Sin internacionalización (i18n)
- Sin manejo de zonas horarias complejas

## Licencia

Este proyecto es para fines educativos y de demostración.
