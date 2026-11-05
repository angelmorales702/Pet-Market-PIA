# Matriz de Progreso - PIA PetMarket

## TAREAS DE BACKEND

- [x] **Tarea 1**: Cancelar un pedido ya pagado: reponer stock (Almacen.reponer)
- [ ] **Tarea 2**: Reembolso de la devolución (US-015): POST /devoluciones/{id}/confirmar-recepcion debe inyectar la pasarela de pago por una dependencia compartida con /pagos. Test que verifique el reembolso y el cierre del pedido.
- [ ] **Tarea 3**: Mapeo central de errores en src/api/main.py: *NoEncontrado* → 404; TransicionEstadoInvalida, CancelacionNoPermitida, DevolucionNoPermitida, StockInsuficiente → 409; validación (método de pago inválido, SKU inválido) → 422. Formato único {"detail": {"codigo", "mensaje"}}. Nunca 500 por errores previsibles. Reemplaza los ValueError "no encontrado" por excepciones de dominio. Actualiza docs/api/errors.md y agrega tests por caso.
- [ ] **Tarea 4**: Test de regresión: guardar el pedido varias veces no cambia líneas ni total (ya existe uno para el pago; agrega uno para preparar, empacar y despachar).
- [ ] **Tarea 5**: Reloj inyectable: verifica que la reserva de 15 min y la ventana de 5 días hábiles usen el reloj inyectado (no datetime.now directo en dominio). Cambia utcnow() por datetime.now(UTC) y HTTP_422_UNPROCESSABLE_ENTITY por HTTP_422_UNPROCESSABLE_CONTENT.

## TAREAS DE ENTREGA

- [ ] **Tarea 6**: docker-compose.yml: servicios db, app y tests, healthcheck en db, `docker compose up` levanta todo y `docker compose run --rm tests` corre la suite contra una base de pruebas propia. Dockerfile con python 3.12-slim, usuario no root, HEALTHCHECK que consulte /health, y que uvicorn escuche en 0.0.0.0:${PORT:-8000}. Las migraciones de Alembic corren al arrancar la app.
- [ ] **Tarea 7**: .github/workflows/ci.yml: Python 3.12, servicio postgres, jobs de lint (ruff), tests con REQUIRE_DB=1 y TEST_DATABASE_URL, gate de cobertura --cov-fail-under=80, y build de la imagen Docker. Corrige todo lo que ruff reporte.
- [ ] **Tarea 8**: Despliegue en Render: render.yaml (Blueprint) con el servicio web de Docker, healthCheckPath /health, DATABASE_URL tomado de la base administrada, y variables de entorno documentadas en .env.example. No inventes límites del plan gratuito; indícalo como pendiente de verificar en la documentación vigente de Render.
- [ ] **Tarea 9**: Exporta docs/api/openapi.json desde la app (script reproducible en scripts/).
- [ ] **Tarea 10**: docs/architecture/SOLID.md con un ejemplo concreto del código para cada principio, con rutas de archivo y fragmentos reales.
- [ ] **Tarea 11**: TRAZABILIDAD.md actualizada (US → caso de uso → endpoint → test, incluida US-016) y SUPUESTOS.md al día.
- [ ] **Tarea 12**: README.md: qué es el proyecto, cómo correr con un comando, cómo correr los tests, variables de entorno, cómo desplegar en Render, endpoints principales, y una sección "Limitaciones conocidas" honesta (por ejemplo: sin autenticación real, X-Cliente-Id como supuesto, autorización de Atención al cliente por bandera en la petición, pasarela de pago simulada).

## Estado Actual
- Rama: fix/tests-api
- Tests pasando: en proceso
- Cobertura: por verificar