# BRD - Business Requirements Document: PetMarket

## 1. Visión General del Proyecto
PetMarket es una plataforma e-commerce especializada en productos para mascotas. El sistema gestiona desde la visualización del catálogo, la división logística de pedidos en múltiples almacenes mediante **Surtidos**, el procesamiento de pagos, la preparación/empaquetado, la entrega de mercancía y el flujo de devoluciones o cancelaciones.

---

## 2. Glosario de Términos del Negocio (Unidades 2 y 3)

- **Cliente**: Persona registrada en la plataforma identificada de manera única por `X-Cliente-Id`.
- **Producto**: Artículo del catálogo identificado por un `Sku` único, con precio (`Dinero`), categoría y descripción.
- **Almacén**: Instalación logística donde se almacenan existencias de productos.
- **ExistenciaProducto**: Cantidad física disponible de un producto en un almacén específico.
- **Pedido**: Solicitud de compra efectuada por un Cliente que agrupa una o varias líneas de pedido.
- **Línea de Pedido**: Detalle dentro de un Pedido que indica el producto (`Sku`), cantidad solicitada y precio unitario.
- **Surtido**: Sub-unidad de un Pedido asignada a un Almacén específico. Un Pedido se divide en uno o más Surtidos según la disponibilidad de existencias.
- **Pago**: Transacción financiera vinculada a un Pedido para cubrir el monto total.
- **Envío**: Operación logística para transportar los Surtidos de un Pedido hacia la dirección de entrega.
- **Guía**: Código de rastreo otorgado por el proveedor de transporte para el seguimiento del Envío.
- **IntentoEntrega**: Registro de cada oportunidad en que el transportista acude a la dirección del Cliente a entregar el envío.
- **Devolución**: Solicitud del Cliente para retornar artículos de un Pedido entregado y recibir un reembolso.

---

## 3. Requerimientos de Negocio (BRD)

### BRD-01: Catálogo y Productos
El sistema debe permitir consultar productos disponibles, filtrando por categoría (Alimentos, Accesorios, Higiene/Otros) y buscando por nombre/SKU.

### BRD-02: Inventario Multi-almacén
El inventario está distribuido en múltiples almacenes. Cada almacén registra la existencia actual de cada SKU.

### BRD-03: Checkout y Creación de Pedido con Surtidos
Al realizar el checkout, el sistema debe evaluar el inventario mediante el `AsignacionAlmacenService` y dividir el pedido en **Surtidos** según la disponibilidad de stock por almacén.

### BRD-04: Procesamiento de Pago
Todo pedido requiere aprobación de pago. El estado del pedido evoluciona de `CREADO` a `PAGADO` cuando el pago es autorizado.

### BRD-05: Preparación y Empaquetado por Surtido
Cada Surtido pasa independientemente por los estados `PENDIENTE`, `EN_PREPARACION` y `EMPACADO`. Un Pedido pasa a estado `EMPACADO` **únicamente cuando TODOS sus Surtidos han sido empacados** (ADR-002).

### BRD-06: Envío y Gestión de Entregas
Una vez empacado, se genera la Guía de envío. Se registran Intentos de Entrega. Si se supera el límite de intentos (por defecto 3), la entrega pasa a fallida.

### BRD-07: Cancelación de Pedidos
Un Cliente puede cancelar su pedido antes de que este se encuentre en estado `ENVIADO`. Se verifica mediante la especificación `PedidoCancelable`.

### BRD-08: Devoluciones
Un Cliente puede solicitar la devolución de un Pedido en estado `ENTREGADO`.

### BRD-09: Trazabilidad y Estado del Pedido
El Cliente debe poder visualizar el estado global del Pedido, la línea de tiempo de transiciones de estado y el detalle/estado individual de cada Surtido.

---

## 4. User Stories & Gherkin Specifications

### US-01: Búsqueda y Filtro en Catálogo
**Como** Cliente  
**Quiero** consultar los productos filtrados por categoría y nombre  
**Para** seleccionar los artículos de mi interés.

```gherkin
Feature: Búsqueda en catálogo
  Scenario: Filtrar productos por categoría
    Given existen productos de la categoría "Alimentos" y "Accesorios"
    When el cliente filtra por la categoría "Alimentos"
    Then el sistema retorna únicamente los productos pertenecientes a "Alimentos"
```

### US-02: Checkout con Asignación de Surtidos
**Como** Sistema de Pedidos  
**Quiero** dividir el pedido en Surtidos por Almacén  
**Para** optimizar el despacho según disponibilidad de existencias.

```gherkin
Feature: División de pedido en surtidos
  Scenario: Asignación exitosa a dos almacenes
    Given un carrito con SKU-1 (2 unidades) y SKU-2 (1 unidad)
    And el Almacén A tiene stock de SKU-1 y el Almacén B tiene stock de SKU-2
    When se procesa el checkout del pedido
    Then se crea el Pedido con 2 Surtidos (uno para Almacén A y otro para Almacén B)
```

### US-03: Procesamiento de Pago
**Como** Cliente  
**Quiero** pagar mi pedido con tarjeta o método digital  
**Para** que sea preparado y despachado.

```gherkin
Feature: Pago de Pedido
  Scenario: Pago aprobado exitosamente
    Given un pedido en estado "CREADO" por un monto de $500 MXN
    When se procesa la transacción de pago aprobada
    Then el estado del pedido cambia a "PAGADO"
    And se emite el evento de dominio "PagoAprobadoEvent"
```

### US-04: Empaquetado Parcial y Completo de Surtidos
**Como** Personal de Almacén  
**Quiero** marcar cada surtido como empacado  
**Para** que el pedido avance a la etapa de envío cuando todos estén listos.

```gherkin
Feature: Empaquetado por surtido
  Scenario: Cambio a Empacado sólo cuando todos los surtidos están listos
    Given un pedido en estado "PAGADO" con 2 surtidos
    When el primer surtido se marca como "EMPACADO"
    Then el pedido permanece en estado "PAGADO"
    When el segundo surtido se marca como "EMPACADO"
    Then el pedido cambia a estado "EMPACADO"
```

### US-05: Envío y Asignación de Guía
**Como** Sistema Logístico  
**Quiero** generar una guía de despacho para el pedido empacado  
**Para** iniciar la distribución.

```gherkin
Feature: Envío de pedido
  Scenario: Generación de envío y cambio de estado
    Given un pedido en estado "EMPACADO"
    When se despacha el pedido con el número de guía "TRACK-12345"
    Then el estado del pedido cambia a "ENVIADO"
```

### US-06: Intentos de Entrega y Entrega Exitosa
**Como** Repartidor  
**Quiero** registrar cada intento de entrega  
**Para** notificar la recepción o registrar fallos.

```gherkin
Feature: Registro de Entrega
  Scenario: Entrega confirmada
    Given un pedido en estado "ENVIADO"
    When se registra un intento de entrega exitoso
    Then el estado del pedido cambia a "ENTREGADO"
```

### US-07: Cancelación de Pedido
**Como** Cliente  
**Quiero** cancelar mi pedido mientras no haya sido enviado  
**Para** solicitar el reembolso de mi dinero.

```gherkin
Feature: Cancelación de Pedido
  Scenario: Cancelar pedido en estado PAGADO
    Given un pedido en estado "PAGADO"
    When el cliente solicita la cancelación
    Then el pedido cambia a estado "CANCELADO"
```

### US-08: Devolución de Pedido
**Como** Cliente  
**Quiero** solicitar la devolución de un pedido entregado  
**Para** retornar los productos no deseados.

```gherkin
Feature: Devolución de Pedido
  Scenario: Solicitar devolución de pedido entregado
    Given un pedido en estado "ENTREGADO"
    When el cliente solicita la devolución especificando el motivo
    Then se crea el registro de Devolución
    And el pedido cambia a estado "DEVOLUCION_SOLICITADA"
```

---

## 5. Descripción de Procesos BPMN

1. **Proceso de Checkout y Asignación**:
   - `Inicio` -> `Recibir Carrito` -> `Ejecutar AsignacionAlmacenService` -> `Crear Pedido y Surtidos` -> `Esperar Pago` -> `Fin`.
2. **Proceso de Empaque**:
   - `Inicio` -> `Surtido Pendiente` -> `Empacar Surtido` -> `¿Todos los Surtidos Empacados?` -> `[Sí]: Transicionar Pedido a EMPACADO` / `[No]: Mantener estado`.
3. **Proceso de Envío y Devolución**:
   - `Empacado` -> `Despachar y Asignar Guía` -> `En tránsito` -> `Registrar Intento Entrega` -> `¿Entregado?` -> `[Sí]: ENTREGADO` -> `Opción Devolución` / `[No]: Reintento o ENTREGA_FALLIDA`.
