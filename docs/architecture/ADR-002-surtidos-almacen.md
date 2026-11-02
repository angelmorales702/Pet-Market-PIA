# ADR-002: División del Pedido en Surtidos por Almacén

## Estatus
Aprobado

## Contexto
PetMarket opera con múltiples almacenes regionales. Un solo pedido del cliente puede contener artículos situados en almacenes distintos, o un solo almacén puede no contar con el stock total requerido.

## Decisión
1. Modela el concepto de **Surtido** como una Entidad contenida exclusivamente dentro del Aggregate **Pedido**.
2. Un Pedido contiene una lista de Surtidos (`List[Surtido]`). Cada Surtido referencia a un `almacen_id` y contiene una o más líneas de producto.
3. Cada Surtido evoluciona su estado operativo de forma independiente (`PENDIENTE` -> `EN_PREPARACION` -> `EMPACADO`).
4. **Regla de Consolidación de Pedido**: El Pedido transiciona de estado `PAGADO` a `EMPACADO` **únicamente cuando TODOS sus surtidos asociados alcancen el estado `EMPACADO`**.

## Consecuencias
- **Positivas**:
  - Refleja fielmente la realidad operativa de logística multi-almacén.
  - Permite empaquetado y preparación concurrente en almacenes físicos distintos.
- **Negativas**:
  - Requiere evaluar el estado de todos los surtidos en cada evento de actualización de empaque.
