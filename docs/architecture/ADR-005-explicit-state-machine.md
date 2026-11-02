# ADR-005: Máquina de Estados Explícita para Pedido

## Estatus
Aprobado

## Contexto
El flujo del `Pedido` pasa por múltiples estados (`CREADO`, `PAGADO`, `EMPACADO`, `ENVIADO`, `ENTREGADO`, `ENTREGA_FALLIDA`, `CANCELADO`, `DEVOLUCION_SOLICITADA`, `DEVUELTO`). Transiciones inválidas (por ejemplo, intentar pasar un pedido de `CREADO` directamente a `ENTREGADO`) deben ser rechazadas con excepciones de dominio explícitas.

## Decisión
1. Implementar una **State Machine explícita** dentro de `src/domain/state_machine.py` **sin librerías externas**.
2. Definir una tabla de transiciones permitidas con guardas explícitas:
   - `CREADO` -> `PAGADO` (Guard: Pago exitoso registrado)
   - `CREADO` / `PAGADO` / `EMPACADO` -> `CANCELADO` (Guard: No despachado)
   - `PAGADO` -> `EMPACADO` (Guard: Todos los surtidos empacados)
   - `EMPACADO` -> `ENVIADO` (Guard: Guía asignada)
   - `ENVIADO` -> `ENTREGADO` (Guard: Intento de entrega exitoso)
   - `ENVIADO` -> `ENTREGA_FALLIDA` (Guard: Intentos agotados)
   - `ENTREGADO` -> `DEVOLUCION_SOLICITADA` (Guard: Solicitud de devolución)
   - `DEVOLUCION_SOLICITADA` -> `DEVUELTO` (Guard: Inspección de devolución aprobada)
3. Si se solicita una transición no registrada en la tabla de transiciones permitidas, se lanza la excepción `TransicionEstadoInvalidaException`.

## Consecuencias
- **Positivas**:
  - Control total sobre las reglas del ciclo de vida del pedido.
  - Cero dependencias de paquetes de terceros.
- **Negativas**:
  - Requiere mantener actualizada la tabla de transiciones ante cambios en el modelo de negocio.
