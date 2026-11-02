# ADR-004: Patrón Specification para Reglas Combinables de Negocio

## Estatus
Aprobado

## Contexto
En PetMarket existen reglas de validación complejas que se reutilizan en múltiples casos de uso y que requieren combinar criterios lógicos (AND, OR, NOT). Por ejemplo: determinar si un producto está disponible para compra, si un pago es aprobable, o si un pedido reúne los requisitos para ser cancelado.

## Decisión
Implementar el patrón **Specification** en la capa de dominio (`src/domain/specifications`):
1. **Clase Base Abstracta `Specification[T]`**: Define el método `is_satisfied_by(candidate: T) -> bool` y los operadores combinadores (`and_`, `or_`, `not_`).
2. **Especificaciones Concretas**:
   - `ProductoDisponibleSpec`: Verifica que un producto esté activo y tenga stock suficiente.
   - `PedidoCancelableSpec`: Verifica que el estado del pedido permita la cancelación (no enviado ni entregado).
   - `DireccionValidaSpec`: Verifica que la dirección de entrega cumpla los criterios mínimos de código postal y ciudad.
   - `PagoAprobableSpec`: Verifica que el monto coincida con el total del pedido y el estado sea idóneo.
3. Las especificaciones se emplean directamente en los casos de uso de la capa de aplicación.

## Consecuencias
- **Positivas**:
  - Reutilización pura de reglas de negocio en distintas partes del sistema.
  - Evaluación limpia de combinaciones lógicas compuestas.
- **Negativas**:
  - Creación de clases adicionales para reglas simples.
