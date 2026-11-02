# ADR-003: Service Layer desacoplado y Domain Events

## Estatus
Aprobado

## Contexto
Los casos de uso de la aplicación deben orquestar las operaciones de dominio y persistencia sin cargar lógica de negocio. Además, ciertas acciones (como notificaciones, actualización de stocks o facturación) son efectos secundarios que no deben bloquear el flujo directo de la transacción principal.

## Decisión
1. **Service Layer (`src/application`)**: Implementa la orquestación de casos de uso (Checkout, CancelarPedido, ProcesarPago, etc.). Los servicios no contienen reglas de negocio; simplemente cargan agregados, invocan métodos de dominio o especificaciones, persisten cambios y emiten eventos.
2. **Domain Events (`src/domain/events`)**: Los agregados registran eventos de dominio (ej. `PedidoCreadoEvent`, `PagoAprobadoEvent`, `PedidoEmpacadoEvent`, `PedidoEnviadoEvent`) cuando ocurren cambios de estado relevantes.
3. Un Event Dispatcher / Handler orquesta los efectos secundarios de manera limpia.

## Consecuencias
- **Positivas**:
  - Separación clara de responsabilidades (Single Responsibility Principle).
  - Facilidad para extender capacidades agregando nuevos suscriptores de eventos sin alterar los servicios ni agregados existentes.
- **Negativas**:
  - Ligero incremento en la complejidad estructural con la introducción de controladores de eventos.
