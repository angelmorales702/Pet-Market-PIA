# Architecture Decision Records · PetMarket

## ADR-001: Usar Domain Model como patrón de lógica de negocio

- **Estado:** Aceptada
- **Contexto:** El proceso de PetMarket tiene un ciclo de vida con muchos estados, múltiples excepciones (pago rechazado, agotado, cancelación, entrega fallida, devolución) y dos almacenes. Las reglas cambiarán con el tiempo.
- **Decisión:** Implementar la lógica con un Domain Model (Aggregates, Entidades y Value Objects), siguiendo DDD.
- **Alternativas consideradas:** Transaction Script, Table Module, Active Record.
- **Consecuencias:**
  - (+) Reglas centralizadas, fáciles de probar y alineadas al lenguaje del negocio.
  - (+) El flujo con estados queda controlado por los propios objetos.
  - (−) Mayor esfuerzo y curva de aprendizaje al inicio.

## ADR-002: Modelar el pedido dividido con Surtidos dentro del Aggregate Pedido

- **Estado:** Aceptada
- **Contexto:** Un mismo pedido puede tomar existencias de ambos almacenes, lo que complica tiempos y el estado real del pedido.
- **Decisión:** `Pedido` es el Aggregate Root y contiene un `Surtido` por cada almacén involucrado. El pedido avanza a "Empacado" solo cuando todos sus surtidos están empacados.
- **Alternativas consideradas:** Crear un pedido independiente por almacén; manejar el split solo en inventario.
- **Consecuencias:**
  - (+) El cliente ve un solo pedido y un estado coherente.
  - (+) La regla "todos los surtidos listos" vive en un solo lugar.
  - (−) El Aggregate Pedido es un poco más grande.

## ADR-003: Service Layer que solo orquesta y eventos de dominio para efectos colaterales

- **Estado:** Aceptada
- **Contexto:** Casos de uso como confirmar checkout o cancelar involucran varios agregados (Pedido, Almacén, Pago).
- **Decisión:** Los Application Services tienen un método por caso de uso y no contienen reglas de negocio: cargan agregados, invocan sus métodos, guardan y publican Domain Events. Acciones secundarias (notificar al cliente, avisar al almacén) reaccionan a eventos en vez de ir dentro de métodos como `confirmar()`.
- **Alternativas consideradas:** Lógica dentro de los servicios; llamadas directas entre agregados.
- **Consecuencias:**
  - (+) Dominio desacoplado de correo, almacén y pasarela de pago.
  - (+) Fácil agregar nuevos efectos sin tocar el dominio.
  - (−) Hay que gestionar la publicación y manejo de eventos.
