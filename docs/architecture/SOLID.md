# Demostración de Principios SOLID en PetMarket

El diseño de PetMarket demuestra la aplicación rigurosa de los principios SOLID en la arquitectura del backend:

---

## 1. Single Responsibility Principle (SRP)
- **Concepto**: Cada módulo o clase debe tener una sola razón para cambiar.
- **Ejemplo en Código**:
  - `Pedido` (Agregado de Dominio): Su única responsabilidad es mantener la consistencia de las líneas de pedido, surtidos y transicionar de estado. No sabe nada de SQL, ni de respuestas HTTP JSON.
  - `AsignacionAlmacenService` (Domain Service): Su única función es determinar cómo se dividen los productos entre los almacenes disponibles según el inventario.
  - `PedidoRepository` (Infraestructura): Su única responsabilidad es guardar y recuperar agregados del almacén de datos PostgreSQL.

---

## 2. Open/Closed Principle (OCP)
- **Concepto**: Las entidades de software deben estar abiertas a la extensión pero cerradas a la modificación.
- **Ejemplo en Código**:
  - `Specification[T]` (`src/domain/specifications/base.py`): Permite añadir nuevas reglas de negocio (ej. `PagoAprobableSpec`, `PedidoCancelableSpec`) extendiendo de `Specification` sin modificar el código que evalúa o combina especificaciones (`and_`, `or_`, `not_`).
  - `EstrategiaAsignacionAlmacen`: Permite inyectar nuevas estrategias de asignación (ej. menor número de envíos vs almacén más cercano) sin alterar los servicios de aplicación.

---

## 3. Liskov Substitution Principle (LSP)
- **Concepto**: Las subclases o implementaciones deben ser sustituibles por sus tipos base sin alterar el funcionamiento correcto del programa.
- **Ejemplo en Código**:
  - `IPedidoRepository` (Interface/Protocol): La capa de aplicación depende de la abstracción `IPedidoRepository`. Se puede sustituir `PostgresPedidoRepository` por `InMemoryPedidoRepository` durante las pruebas unitarias sin romper la ejecución ni requerir cambios en el servicio de aplicación.

---

## 4. Interface Segregation Principle (ISP)
- **Concepto**: Los clientes no deben estar obligados a depender de interfaces que no utilizan.
- **Ejemplo en Código**:
  - En lugar de un único repositorio monolítico para todo el sistema, cada Agregado posee su interfaz de repositorio especializada: `IPedidoRepository`, `IProductoRepository`, `IAlmacenRepository`. Los servicios solo solicitan las interfaces que realmente necesitan.

---

## 5. Dependency Inversion Principle (DIP)
- **Concepto**: Los módulos de alto nivel no deben depender de módulos de bajo nivel. Ambos deben depender de abstracciones.
- **Ejemplo en Código**:
  - La capa `src/domain` no importa nada de `src/infrastructure` ni de `fastapi` o `sqlalchemy`.
  - La capa `src/application` depende de las interfaces (Protocols/Abstract Classes) definidas en `src/domain/repositories/`. La inyección de dependencias concreta (SQLAlchemy repositories) se realiza en el punto de entrada de la API (`src/api/dependencies.py`).
