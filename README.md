# PetMarket - Sistema de E-commerce para Mascotas

Sistema de e-commerce implementado con **Clean Architecture + DDD**, PostgreSQL, SQLAlchemy 2.0 y FastAPI.

## Tecnologías

- **Python 3.11+** con FastAPI
- **PostgreSQL 16** con SQLAlchemy 2.0 (Declarative)
- **Alembic** para migraciones
- **Docker** para despliegue
- **State Machine Pattern** para transiciones de estado de dominio

## Arquitectura

El proyecto sigue los principios de Clean Architecture y Domain-Driven Design (DDD):

- **Dominio**: Aggregates (Pedido, Cliente, Producto, Almacen, Pago, Envio, Devolucion), Entities, Value Objects y State Machine
- **Aplicación**: Ports, Adapters, Use Cases
- **Infraestructura**: SQLAlchemy 2.0, Alembic, Repositorios

### ADR Principales

- **ADR-002/003**: No ForeignKey constraints entre aggregates distintos (referencian solo por ID)
- **ADR-006**: Columnas `estado` como String(50), validación en el dominio

## Requisitos

- Python 3.11+
- PostgreSQL 16
- Docker y Docker Compose

## Instalación

### 1. Clonar el repositorio

```bash
git clone <repository-url>
cd PetMarket
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

### Documentación

Una vez arrancada la API, visita:
- **Swagger/OpenAPI**: http://localhost:8000/docs
- **Redoc**: http://localhost:8000/redoc

### Health Check

```bash
curl http://localhost:8000/health
# Respuesta: {"status": "healthy", "service": "petmarket-api"}
```

## Endpoints

| Endpoint | Método | Descripción | User Story |
|----------|--------|-------------|------------|
| `/health` | GET | Health check | - |
| `/productos` | GET | Listar productos del catálogo | US-001 |
| `/productos/{sku}` | GET | Detalles de un producto | US-001 |
| `/almacenes` | GET | Listar almacenes | - |
| `/almacenes/{id}/inventario` | GET | Inventario de un almacén | US-001 |
| `/pedidos` | POST | Crear pedido (checkout) | US-004 |
| `/pedidos/{id}` | GET | Consultar estado de pedido | US-012 |
| `/clientes/{id}/pedidos` | GET | Listar pedidos de cliente | US-012 |
| `/pedidos/{id}/cancelar` | POST | Cancelar pedido | US-008, US-009 |
| `/pedidos/{id}/iniciar-preparacion` | POST | Iniciar preparación | US-007 |
| `/pedidos/{id}/confirmar-empaque` | POST | Confirmar empaquetado | US-007 |
| `/pedidos/{id}/enviar` | POST | Despachar con guía | US-006 |
| `/pedidos/{id}/entrega` | POST | Registrar entrega | US-010, US-011 |
| `/pagos` | POST | Procesar pago | US-003, US-004 |
| `/devoluciones` | POST | Solicitar devolución | US-013, US-014 |
| `/devoluciones/{id}/autorizar` | POST | Autorizar devolución | US-014 |
| `/devoluciones/{id}/rechazar` | POST | Rechazar devolución | US-014 |
| `/devoluciones/{id}/confirmar-recepcion` | POST | Confirmar recepción almacén | US-014, US-015 |
| `/almacenes/{id}/discrepancia` | POST | Detectar discrepancia inventario | US-016 |

## Pruebas

### Ejecutar tests

```bash
# Tests con PostgreSQL
REQUIRE_DB=1 pytest tests/ --cov=src --cov-fail-under=80

# O usar Docker para la base de test
docker compose up -d db
docker compose --profile tests run --rm tests
```

### Ejecutar tests con Docker Compose

```bash
# Levantar servicios
docker compose up -d db

# Ejecutar tests contra base de test propia
docker compose --profile tests run --rm tests
```

### Tests de Integración API

```bash
python -m pytest tests/test_api.py -v
```

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

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `DATABASE_URL` | URL de conexión PostgreSQL | `postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db` |
| `TEST_DATABASE_URL` | URL para tests | `postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_test` |
| `CORS_ORIGINS` | Orígenes permitidos CORS | `*` |
| `PORT` | Puerto de la API | `8000` |
| `ENVIRONMENT` | Entorno (development/production) | `development` |
| `MAX_INTENTOS_ENTREGA` | Máximo intentos entrega | `3` |
| `PLAZO_CANCELACION_DIAS` | Plazo cancelación en días | `2` |
| `ESTRATEGIA_ASIGNACION_ALMACEN` | Estrategia asignación almacén | `MENOR_NUMERO_ALMACENES` |

Ver `.env.example` para configuración completa.

## Despliegue

### Docker

```bash
docker compose build
docker compose up -d app db
```

### Despliegue en Render

1. Conectar repositorio a Render
2. Render detecta `render.yaml` (Blueprint)
3. Crear base de datos PostgreSQL administrada
4. Conectar base de datos al servicio web
5. Render ejecuta Docker, migraciones y health check `/health`

### Después del deploy

```bash
# Ejecutar migraciones
docker compose exec app alembic upgrade head

# Seed de datos
docker compose exec app python scripts/seed_data.py
```

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