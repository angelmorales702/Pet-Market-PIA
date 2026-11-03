# ADR-003: Service Layer que solo orquesta y eventos de dominio para efectos colaterales

## Estatus
Aprobado

## Contexto
Casos de uso como confirmar checkout o cancelar involucran varios agregados (Pedido, Almacén, Pago).

## Decisión
Los Application Services tienen un método por caso de uso y no contienen reglas de negocio: cargan agregados, invocan sus métodos, guardan y publican Domain Events. Acciones secundarias (notificar al cliente, avisar al almacén) reaccionan a eventos en vez de ir dentro de métodos como `confirmar()`.

## Consecuencias
- (+) Dominio desacoplado de correo, almacén y pasarela de pago.
- (+) Fácil agregar nuevos efectos sin tocar el dominio.
- (−) Hay que gestionar la publicación y manejo de eventos.