# ADR-001: Domain Model con DDD (Domain-Driven Design)

## Estatus
Aprobado

## Contexto
El negocio de PetMarket maneja lógica transaccional compleja: la división de pedidos en surtidos por almacén, el ciclo de vida estricto del pedido, las reglas de validación de pagos, cancelaciones y devoluciones. Mezclar lógica de negocio con frameworks de persistencia o controladores genera código acoplado y difícil de probar.

## Decisión
Adoptar el patrón **Domain Model** impulsado por **DDD (Domain-Driven Design)**:
1. **Aggregates**: Pedido, Almacen, Pago, Envio, Devolucion, Cliente, Producto.
2. **Entities**: LineaPedido, Surtido (dentro de Pedido), ExistenciaProducto (dentro de Almacen), IntentoEntrega (dentro de Envio), LineaDevolucion (dentro de Devolucion).
3. **Value Objects**: Dinero, DireccionEntrega, Sku, Guia, ModalidadEntrega, MotivoDevolucion.
4. Las reglas de negocio se implementan puramente dentro de la capa `src/domain` sin dependencias de frameworks externos (FastAPI, SQLAlchemy, etc.).
5. Los agregados se relacionan **únicamente por identificador** (ej. `Surtido.almacen_id: UUID`), garantizando límites transaccionales independientes.

## Consecuencias
- **Positivas**:
  - Mantenibilidad y alta testeabilidad mediante pruebas unitarias puras en `domain/`.
  - Independencia total de la infraestructura (base de datos o framework HTTP).
- **Negativas**:
  - Requiere mapeo explícito entre modelos de dominio y modelos ORM en la capa de infraestructura.