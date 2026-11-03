# ADR-002: Modelar el pedido dividido con Surtidos dentro del Aggregate Pedido

## Estatus
Aprobado

## Contexto
Un mismo pedido puede tomar existencias de ambos almacenes, lo que complica tiempos y el estado real del pedido.

## Decisión
`Pedido` es el Aggregate Root y contiene un `Surtido` por cada almacén involucrado. El pedido avanza a "Empacado" solo cuando todos sus surtidos están empacados.

## Consecuencias
- (+) El cliente ve un solo pedido y un estado coherente.
- (+) La regla "todos los surtidos listos" vive en un solo lugar.
- (−) El Aggregate Pedido es un poco más grande.