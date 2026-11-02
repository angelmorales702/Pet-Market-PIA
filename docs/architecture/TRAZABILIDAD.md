# Matriz de Trazabilidad - PetMarket

Esta matriz garantiza la trazabilidad bidireccional completa entre las necesidades de negocio (BRD), User Stories, criterios de aceptación Gherkin, clases/reglas de dominio y las pruebas automatizadas (unitarias e integración).

| Necesidad BRD | User Story | Criterio Gherkin | Regla / Clase de Dominio | Test Asociado |
| :--- | :--- | :--- | :--- | :--- |
| **BRD-01** | **US-01** (Catálogo) | Scenario: Filtrar productos por categoría | `Producto` (Aggregate), `Sku` (VO), `ProductoDisponibleSpec` | `tests/unit/domain/test_producto.py::test_filtrar_catalogo` |
| **BRD-02** | **US-01** (Inventario) | Scenario: Consultar stock por almacén | `Almacen` (Aggregate), `ExistenciaProducto` | `tests/unit/domain/test_almacen.py::test_existencias_almacen` |
| **BRD-03** | **US-02** (Checkout) | Scenario: Asignación exitosa a dos almacenes | `AsignacionAlmacenService`, `Surtido` (Entity), `Pedido` (Aggregate) | `tests/unit/domain/test_asignacion_almacen.py::test_asignacion_multi_almacen` |
| **BRD-04** | **US-03** (Pago) | Scenario: Pago aprobado exitosamente | `Pago` (Aggregate), `PagoAprobableSpec`, `PagoAprobadoEvent` | `tests/unit/domain/test_pago.py::test_pago_aprobable` |
| **BRD-05** | **US-04** (Empaquetado) | Scenario: Cambio a Empacado sólo cuando todos los surtidos están listos | `Pedido.marcar_surtido_empacado`, `PedidoStateMachine` | `tests/unit/domain/test_state_machine.py::test_empaque_surtidos_completo` |
| **BRD-06** | **US-05** (Envío) | Scenario: Generación de envío y cambio de estado | `Envio` (Aggregate), `Guia` (VO), `PedidoEnviadoEvent` | `tests/unit/domain/test_envio.py::test_despacho_envio` |
| **BRD-06** | **US-06** (Entrega) | Scenario: Entrega confirmada o fallida por intentos | `IntentoEntrega`, `Pedido.marcar_entregado`, `Pedido.marcar_entrega_fallida` | `tests/unit/domain/test_envio.py::test_intentos_entrega` |
| **BRD-07** | **US-07** (Cancelación)| Scenario: Cancelar pedido en estado PAGADO | `PedidoCancelableSpec`, `Pedido.cancelar` | `tests/unit/domain/test_specifications.py::test_pedido_cancelable_spec` |
| **BRD-08** | **US-08** (Devolución) | Scenario: Solicitar devolución de pedido entregado | `Devolucion` (Aggregate), `Pedido.solicitar_devolucion` | `tests/unit/domain/test_devolucion.py::test_solicitar_devolucion` |
| **BRD-09** | **US-02..08** (Trazabilidad) | Scenario: Consulta de estado e hito de Surtidos | `Pedido.obtener_resumen_estado`, `PedidoStateMachine` | `tests/integration/api/test_pedidos_api.py::test_consultar_estado_pedido` |
