# ADR-005: Máquina de Estados Explícita para Pedido

## Estatus
Aprobado

## Contexto
El flujo del `Pedido` pasa por múltiples estados. Transiciones inválidas deben ser rechazadas con excepciones de dominio explícitas.

## Decisión
1. Implementar una **State Machine explícita** dentro de `src/domain/state_machine.py` **sin librerías externas**.
2. Estados: `CREADO`, `PENDIENTE_PAGO`, `PAGADO`, `EN_PREPARACION`, `EMPACADO`, `ENVIADO`, `ENTREGADO`, `CANCELADO`, `ENTREGA_FALLIDA`, `DEVUELTO`.
3. Tabla de transiciones permitidas con guardas explícitas (ver código en `state_machine.py`).
4. Si se solicita una transición no registrada, se lanza `TransicionEstadoInvalidaException`.

## Consecuencias
- (+) Control total sobre las reglas del ciclo de vida del pedido.
- (+) Cero dependencias de paquetes de terceros.
- (−) Requiere mantener actualizada la tabla de transiciones.