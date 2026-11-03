# Matriz de Trazabilidad - PetMarket

Esta matriz garantiza la trazabilidad bidireccional completa entre las necesidades de negocio (BRD), User Stories, criterios de aceptación Gherkin, clases/reglas de dominio y las pruebas automatizadas (unitarias e integración).

| Necesidad BRD | User Story | Criterio Gherkin (Escenario) | Regla / Clase del Dominio | Test Asociado |
| :--- | :--- | :--- | :--- | :--- |
| **N6** | **US-001** | Asegurar disponibilidad de producto durante checkout | `Almacen.reservar()`<br>`StockReservadoEvent` | `test_almacen_reserva_stock` (test_domain_almacen.py) |
| **N6** | **US-002** | Liberación automática de la reserva después de 15 minutos | `Almacen.liberar_reserva()`<br>`ExistenciaProducto.liberar_reserva()` | `test_almacen_liberar_reserva` (test_domain_almacen.py) |
| **N5** | **US-003** | Posibilidad de reintentar el pago tras un intento fallido | `Pedido.marcar_pago_rechazado()`<br>`Pago.rechazar()`<br>`PagoRechazadoEvent` | `test_pedido_reintentos_pago_tres_veces` (test_domain_pedido.py) |
| **N5** | **US-003** | Pago rechazado 3 veces | `Pedido.marcar_pago_rechazado()` (3er llamado)<br>Transición a CANCELADO | `test_pedido_reintentos_pago_tres_veces` (test_domain_pedido.py) |
| **N5** | **US-004** | Compra confirmada tras pago exitoso | `Pedido.marcar_pagado()`<br>`Pago.aprobar()`<br>`PagoAprobadoEvent` | `test_pedido_transicion_a_pagado` (test_domain_pedido.py) |
| **N7** | **US-005** | Agotamiento de un producto durante el proceso de compra | `Almacen.reservar()` lanza `StockInsuficienteError`<br>`StockInsuficienteEvent`<br>Sólo se cancela la línea afectada | `test_almacen_stock_insuficiente` (test_domain_almacen.py)<br>`test_asignacion_almacen_stock_insuficiente` (test_domain_services.py) |
| **N2** | **US-006** | Pedido con productos en dos almacenes | `AsignacionAlmacenService.asignar()`<br>Crea `Surtido` por almacén<br>`PedidoCreadoEvent` con múltiples surtidos | `test_asignacion_almacen_service_dos_almacenes` (test_domain_services.py) |
| **N2** | **US-006** | Un solo número de pedido con dos rastreos | `Pedido.asignar_surtidos()` mantiene un `pedido.id`<br>`Envio` por surtido con `Guia` | `test_asignacion_almacen_service_dos_almacenes` (test_domain_services.py) |
| **N2** | **US-006** | Un único costo de envío prorrateado | `# SUPUESTO: validar con el negocio`<br>Ver `AsignacionAlmacenService` | Pendiente: test de costo de envío |
| **N7** | **US-007** | Almacén recibe pedido para empaquetado | `Pedido.iniciar_preparacion()`<br>`Surtido.marcar_en_preparacion()` | `test_pedido_no_cancelable_despues_de_enviado` (setup usa iniciar_preparacion) |
| **N3** | **US-008** | Cancelación de pedido antes de preparación | `Pedido.cancelar()`<br>`PedidoCancelableSpec`<br>Estados permitidos: CREADO, PENDIENTE_PAGO, PAGADO | `test_pedido_cancelar_cliente_antes_de_preparacion` (test_domain_pedido.py)<br>`test_pedido_cancelable_spec_estado_pagado` (test_domain_especificaciones.py) |
| **N3** | **US-009** | Cancelación después de que el pedido haya entrado en preparación | `Pedido.cancelar()` requiere autorización<br>Estados EN_PREPARACION en adelante: guarda en State Machine<br>`CancelacionNoPermitidaError` para cliente | `test_pedido_no_cancelable_despues_de_enviado` (test_domain_pedido.py)<br>`test_pedido_cancelable_spec_estado_enviado` (test_domain_especificaciones.py) |
| **N7** | **US-010** | Primer intento de entrega exitoso / fallido | `Envio.registrar_intento(exitoso=True/False)`<br>`IntentoEntregaRegistradoEvent`<br>`PedidoEntregadoEvent` | Pendiente: test unitario Envio.registrar_intento |
| **N7** | **US-011** | Segundo intento de entrega exitoso / fallido | `Envio.registrar_intento()` (2da llamada)<br>Si fallido: `EntregaFallidaEvent`<br>Estado `ENTREGA_FALLIDA` | `test_devolucion_flujo_autorizacion_recepcion_reembolso` (simula entrega fallida) |
| **N7** | **US-012** | Reprogramación o reembolso tras entrega fallida | `Pedido.marcar_entrega_fallida()`<br>`EntregaFallidaEvent`<br>Atención al cliente contacta → reprograma o reembolsa | Pendiente: test de reprogramación |
| **N4** | **US-013** | Cliente solicita devolución dentro del plazo aceptado | `Pedido.solicitar_devolucion()`<br>`Devolucion.solicitar()`<br>`DevolucionDentroDeVentanaSpec`<br>`DevolucionSolicitadaEvent` | `test_devolucion_solicitar_dentro_ventana` (test_domain_devolucion.py) |
| **N4** | **US-013** | Cliente solicita devolución fuera del plazo | `Devolucion.esta_dentro_ventana()` retorna False<br>Sistema rechaza | `test_devolucion_fuera_ventana` (test_domain_devolucion.py) |
| **N4** | **US-014** | Atención al cliente autoriza la devolución | `Devolucion.autorizar()`<br>`DevolucionAprobadaEvent` | `test_devolucion_flujo_autorizacion_recepcion_reembolso` (test_domain_devolucion.py) |
| **N4** | **US-014** | Atención al cliente rechaza la devolución | `Devolucion.rechazar()`<br>Estado `RECHAZADA` | Pendiente: test de rechazo de devolución |
| **N4** | **US-014** | Almacén confirma recepción del producto devuelto | `Devolucion.confirmar_recepcion_almacen()`<br>Estado `PROCESADA` | `test_devolucion_flujo_autorizacion_recepcion_reembolso` (test_domain_devolucion.py) |
| **N4** | **US-015** | Reembolso procesado tras confirmación de Almacén | `Devolucion.marcar_reembolsado()`<br>`Pago.reembolsar()` | `test_devolucion_flujo_autorizacion_recepcion_reembolso` (test_domain_devolucion.py) |
| **N1** | **US-016** | Generación del indicador de discrepancia | `Almacen.detectar_discrepancia()`<br>`DiscrepanciaInventarioDetectadaEvent`<br>`DiscrepanciaInventarioSpec` | `test_almacen_detectar_discrepancia` (test_domain_discrepancia.py)<br>`test_discrepancia_inventario_spec_detecta_diferencia` (test_domain_services.py) |

---

## Trazabilidad Técnica Adicional

| Componente | Clase / Archivo | Tests que lo cubren |
|------------|-----------------|---------------------|
| **Value Objects** | `Sku`, `Dinero`, `DireccionEntrega`, `Guia`, `MotivoDevolucion`, `EstadoSurtido`, `EstadoPago`, `EstadoEnvio`, `EstadoDevolucion` | `test_domain_especificaciones_extra.py` (uso en specs) |
| **Entities** | `LineaPedido`, `Surtido`, `ExistenciaProducto`, `IntentoEntrega`, `LineaDevolucion` | `test_domain_almacen.py`, `test_domain_devolucion.py`, `test_domain_pedido.py` |
| **Aggregates** | `Pedido`, `Cliente`, `Producto`, `Almacen`, `Pago`, `Envio`, `Devolucion` | Todos los tests de dominio |
| **Domain Events** | `PedidoCreadoEvent`, `PedidoCanceladoEvent`, `PedidoEmpacadoEvent`, `StockReservadoEvent`, `StockInsuficienteEvent`, `PagoAprobadoEvent`, `PagoRechazadoEvent`, `PedidoEntregadoEvent`, `EntregaFallidaEvent`, `DevolucionSolicitadaEvent`, `DevolucionAprobadaEvent`, `PedidoEnviadoEvent`, `IntentoEntregaRegistradoEvent`, `SurtidoEmpacadoEvent` | Tests que verifican `domain_events` en agregados |
| **State Machine** | `EstadoPedido`, `transitar()`, `TRANSICIONES`, `GUARDAS` | `test_pedido_transicion_invalida`, `test_pedido_transicion_a_pagado`, `test_pedido_cancelar_cliente_antes_de_preparacion` |
| **Specifications** | `Specification` (base), `ProductoDisponibleSpec`, `PedidoCancelableSpec`, `PagoAprobableSpec`, `DireccionValidaSpec`, `DevolucionDentroDeVentanaSpec`, `StockSuficienteSpec`, operadores `and_`, `or_`, `not_` | `test_domain_especificaciones.py`, `test_domain_especificaciones_extra.py` |
| **Domain Services** | `AsignacionAlmacenService` | `test_domain_services.py` |
| **Exceptions** | `StockInsuficienteError`, `PagoRechazadoError`, `TransicionEstadoInvalidaException`, `SurtidoNoEmpacadoError`, `IntentosEntregaAgotadosError`, `PagoMontoNoCoincideError`, `ProductoNoEncontradoError`, `AlmacenNoEncontradoError`, `SurtidoNoEncontradoError`, `DevolucionNoPermitidaError`, `CancelacionNoPermitidaError` | Tests que esperan estas excepciones |

---

## Cobertura de Tests Actual

- **Tests unitarios totales:** 42
- **Cobertura global:** 80.70% (cumple gate de CI ≥80%)
- **Archivos de test:**
  - `tests/test_domain_pedido.py` (7 tests) - US-003, US-004, US-008, US-009
  - `tests/test_domain_almacen.py` (4 tests) - US-001, US-002, US-005
  - `tests/test_domain_devolucion.py` (4 tests) - US-013, US-014, US-015
  - `tests/test_domain_especificaciones.py` (4 tests) - US-004, US-008, US-009
  - `tests/test_domain_especificaciones_extra.py` (11 tests) - US-001, US-002, US-004, US-008, US-013
  - `tests/test_domain_services.py` (10 tests) - US-002, US-005, US-006, US-013, US-016
  - `tests/test_domain_discrepancia.py` (1 test) - US-016

---

*Matriz basada en fuentes oficiales: docs/fuentes/1_BRD_PetMarket.pdf, docs/fuentes/2_UserStories_PetMarket.pdf, docs/fuentes/3_BPMN_PetMarket.pdf, docs/fuentes/4_Glosario_PetMarket.pdf, docs/fuentes/Diagrama_de_clases.md, docs/fuentes/Diagramas_DDD.md, docs/fuentes/ADR.md*