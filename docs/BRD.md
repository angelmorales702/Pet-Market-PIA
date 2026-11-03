# BRD - Business Requirements Document: PetMarket

## 1. Visión General del Proyecto
PetMarket es una tienda en línea de alimentos, accesorios y otros productos para mascotas que opera dos almacenes (Norte y Sur) y ofrece diferentes modalidades de entrega. El proceso actual permite al cliente agregar productos al carrito, validar inventario, domicilio, método de entrega y pago en el checkout, y da seguimiento al pedido a través de pago, preparación, empaque, envío y entrega. Un mismo pedido puede requerir existencias de ambos almacenes.

## 2. Glosario de Términos del Negocio (Unidades 2 y 3 - docs/fuentes/4_Glosario_PetMarket.pdf)

| Término | Definición |
|---------|------------|
| PetMarket | Tienda en línea dedicada a la venta de alimentos, accesorios y otros productos para mascotas. |
| Cliente | Usuario que selecciona productos, realiza compras y consulta el estado de sus pedidos. |
| Producto | Artículo disponible para venta dentro de PetMarket. |
| Carrito de compra | Conjunto temporal de productos seleccionados por el cliente antes de confirmar la compra. |
| Checkout | Etapa de la compra donde se validan inventario, domicilio, método de entrega y pago. |
| Pedido | Registro generado después de que el pago de una compra es confirmado. |
| Detalle de pedido | Información de cada producto que forma parte de un pedido, incluyendo cantidad e importe. |
| Inventario | Registro de las existencias disponibles de un producto en cada almacén. |
| Reserva de inventario | Separación temporal de las existencias durante el checkout. En PetMarket tiene una duración de 15 minutos. |
| Almacén | Ubicación física donde se guardan y preparan los productos. PetMarket opera con los almacenes Norte y Sur. |
| Almacén Norte | Uno de los dos almacenes desde los cuales se preparan los pedidos de PetMarket. |
| Almacén Sur | Segundo almacén utilizado para almacenar y preparar productos. |
| Pedido dividido | Pedido cuyos productos deben prepararse desde ambos almacenes debido a la distribución del inventario. |
| Pago | Operación utilizada para cobrar al cliente el importe correspondiente a su pedido. |
| Pago rechazado | Intento de cobro no autorizado. PetMarket permite hasta tres reintentos durante la misma sesión. |
| Picking | Actividad del almacén que consiste en localizar y seleccionar físicamente los productos correspondientes a un pedido. |
| Empaque | Proceso mediante el cual los productos seleccionados son preparados y protegidos para su envío. |
| Envío | Traslado de un paquete desde el almacén de origen hasta el domicilio del cliente. |
| Rastreo | Información asociada a un envío que permite consultar su progreso. |
| Estatus del pedido | Estado actual en que se encuentra un pedido durante su procesamiento, preparación, envío o entrega. |
| Paquetería / Reparto | Área encargada de trasladar y entregar los paquetes al cliente. |
| Intento de entrega | Acción realizada por Paquetería para entregar un paquete. PetMarket contempla un máximo de dos intentos antes de regresarlo al almacén. |
| Entrega fallida | Situación en la que Paquetería no consigue entregar el paquete al cliente. |
| Cancelación | Terminación de un pedido antes de completar normalmente el proceso. |
| Cancelación tardía | Cancelación solicitada después de que el pedido ha entrado en preparación y que requiere intervención de Atención al cliente. |
| Atención al cliente | Área responsable de autorizar cancelaciones tardías, devoluciones y reprogramaciones. |
| Devolución | Proceso mediante el cual el cliente solicita regresar productos después de haberlos recibido. |
| Ventana de devolución | Periodo disponible para solicitar una devolución. En PetMarket corresponde a cinco días hábiles después de la entrega. |
| Reembolso | Devolución del dinero al cliente realizada por el área de Pagos. |
| Producto agotado | Producto cuya existencia ya no se encuentra disponible durante el proceso de compra. Se cancela únicamente la línea afectada y el resto del pedido continúa. |
| Reprogramación | Asignación de una nueva oportunidad de entrega después de una entrega fallida. |
| Discrepancia de inventario | Diferencia entre la cantidad de productos mostrada como disponible en el sitio y la existencia física real en los almacenes. |
| Número de pedido | Identificador único de una compra. Aunque el pedido se divida entre los almacenes Norte y Sur, se mantiene un solo número. |

## 3. Necesidades del Negocio (del BRD - docs/fuentes/1_BRD_PetMarket.pdf)

- **N1.** Reducir la discrepancia entre inventario web y existencia real en almacén.
- **N2.** Dar visibilidad clara y en tiempo real del estatus del pedido al cliente, incluyendo cuando el pedido está dividido.
- **N3.** Formalizar el flujo de cancelación según el punto del proceso en que se encuentre el pedido.
- **N4.** Formalizar el flujo de devolución con responsables y tiempos claros.
- **N5.** Manejar de forma automática los reintentos de pago rechazado.
- **N6.** Manejar de forma automática la reserva y liberación de inventario durante el checkout.
- **N7.** Reducir la intervención manual entre Almacén, Atención al cliente y Pagos en excepciones (agotado, entrega fallida, devolución).

## 4. Restricciones
- El sistema debe operar sobre los dos almacenes existentes (Norte y Sur), sin asumir un tercer almacén.
- Los métodos de pago y paquetería actuales deben mantenerse (no se define reemplazo de proveedores).
- El proyecto debe entregarse dentro del calendario de las semanas 4-5 del curso.

## 5. Supuestos
- Se asume que el stakeholder simulado representa fielmente las políticas reales de un negocio de este tipo, dado que PetMarket es un caso de estudio.
- Se asume que los tiempos y porcentajes definidos en la entrevista (15 minutos de reserva, 3 reintentos de pago, 2 intentos de entrega, 5 días de devolución, meta de 2% de error de inventario, meta de -40% en tickets) son los valores oficiales de negocio para este ejercicio.
- Se asume que Pagos y Paquetería son áreas/servicios internos y no proveedores externos con SLA propio.

## 6. Criterios de Éxito
| Criterio | Métrica objetivo |
|----------|------------------|
| Precisión de inventario web vs. real | Discrepancia menor al 2% |
| Visibilidad de estatus del pedido | Reducción del 40% en tickets de soporte por "¿dónde está mi pedido?" |
| Manejo automático de pago rechazado | 100% de los pedidos con pago rechazado pasan por el flujo de reintentos sin intervención manual |
| Manejo de pedidos divididos | 100% de los pedidos divididos muestran un solo número de pedido con ambos rastreos al cliente |
| Flujo de devoluciones | 100% de las devoluciones siguen el flujo formal: solicitud → autorización → recepción en almacén → reembolso |

## 7. Requerimientos Funcionales (User Stories - docs/fuentes/2_UserStories_PetMarket.pdf)

### US-001: Reserva de inventario durante checkout
**Como** cliente, **quiero** que los productos añadidos a mi carrito sean reservados por el sistema durante el proceso de checkout **para** asegurar su disponibilidad durante este.
- **Escenario:** Asegurar disponibilidad de producto durante checkout
  - **Given:** el cliente cuenta con productos disponibles en el carrito
  - **When:** el cliente inicia el proceso de checkout
  - **Then:** el sistema realiza la reserva de los productos
  - **And:** la reserva se mantiene activa durante 15 minutos

### US-002: Liberación automática de reserva
**Como** el sistema de PetMarket, **quiero** liberar la reserva de productos en el inventario si el pago no se realiza en 15 minutos **para** evitar pérdidas y bloquear productos a otros clientes.
- **Escenario:** Liberación automática de la reserva después de 15 minutos
  - **Given:** el cliente cuenta con productos en estado de reserva
  - **When:** el cliente no completa el proceso de pago en 15 minutos
  - **Then:** el sistema libera automáticamente la reserva de esos productos

### US-003: Reintentos de pago
**Como** cliente, **quiero** contar con varias oportunidades para completar el proceso de pago **para** tener la certeza de poder completar la compra y no perder mis productos.
- **Escenario:** Posibilidad de reintentar el pago tras un intento fallido
  - **Given:** el cliente se encuentra en el proceso de pago
  - **When:** el pago realizado por el cliente fue rechazado y no ha sido rechazado 3 veces anteriormente
  - **Then:** el cliente contará con otra oportunidad de pago
- **Escenario:** Pago rechazado 3 veces
  - **Given:** el cliente se encuentra en proceso de pago
  - **When:** el pago fue rechazado y ya había sido rechazado 3 veces anteriormente
  - **Then:** el cliente ya no cuenta con otra oportunidad de pago
  - **And:** el pedido es cancelado automáticamente

### US-004: Compra confirmada tras pago exitoso
**Como** cliente, **quiero** que tras realizar el pago de mi pedido exitosamente este sea creado y confirmado **para** contar con la seguridad de que mi compra fue realizada correctamente.
- **Escenario:** Compra confirmada tras pago exitoso
  - **Given:** el cliente completó el proceso de checkout correctamente
  - **When:** el pago ha sido aprobado
  - **Then:** el sistema crea y confirma el pedido

### US-005: Producto agotado durante compra
**Como** cliente, **quiero** que si un producto de mi carrito se agota durante mi proceso de compra no se cancele el pedido completo, **sino** que solo se remueva ese producto, **para** no perder mi pedido completo.
- **Escenario:** Agotamiento de un producto durante el proceso de compra
  - **Given:** el cliente se encuentra en proceso de compra
  - **When:** un producto del pedido se agota
  - **Then:** se cancela solo la preparación de ese producto
  - **And:** el resto del pedido puede seguir con el proceso de compra

### US-006: Pedido dividido entre almacenes
**Como** sistema de PetMarket, **quiero** poder realizar pedidos con existencias en ambos almacenes **para** que cada almacén prepare sus productos respectivamente.
- **Escenario:** Pedido con productos en dos almacenes
  - **Given:** una compra realizada por un cliente requiere productos de dos almacenes
  - **When:** el sistema reconoce y asigna el pedido a cada almacén
  - **Then:** divide la compra en dos sub-pedidos
  - **And:** el sistema crea un solo número de pedido con dos rastreos asociados
  - **And:** se cobra un único costo de envío

### US-007: Preparación y empaquetado por almacén
**Como** operador de almacén, **quiero** recibir mi pedido o sub-pedido para preparación **para** realizar el proceso de empaquetado.
- **Escenario:** Almacén recibe pedido para empaquetado
  - **Given:** un almacén recibe un pedido o sub-pedido para realizar
  - **When:** se le asigna el pedido a un operador del almacén
  - **Then:** el operador realiza el picking y el empaquetado para su entrega

### US-008: Cancelación antes de preparación
**Como** cliente, **quiero** poder cancelar mi pedido siempre y cuando aún no se encuentre en preparación **para** poder cancelar sin repercusiones.
- **Escenario:** Cancelación de pedido antes de preparación
  - **Given:** el cliente cuenta con un pedido pagado
  - **When:** el cliente realiza una cancelación antes de que el pedido entre en proceso de preparación
  - **Then:** el pedido es cancelado sin penalización alguna
  - **And:** se libera la reserva de los productos en el pedido

### US-009: Cancelación después de preparación (tardía)
**Como** cliente, **quiero** poder realizar la cancelación de mi pedido después de que haya entrado en preparación **para** poder contar con esa opción aunque implique una autorización.
- **Escenario:** Cancelación después de que el pedido haya entrado en preparación
  - **Given:** el cliente cuenta con un pedido pagado
  - **When:** el cliente realiza una cancelación después de que el pedido entre en proceso de preparación
  - **Then:** la solicitud es enviada a Atención al cliente para su autorización
  - **And:** el pedido es cancelado solo después de su autorización

### US-010: Intentos de entrega
**Como** repartidor de paquetería, **quiero** registrar el estado de mi primer intento de entrega **para** que el sistema sepa si el pedido fue entregado exitosamente o si se debe programar otro intento.
- **Escenario:** Primer intento de entrega exitoso
  - **Given:** un paquete está en ruta para su primer intento de entrega
  - **When:** el repartidor entrega el paquete al cliente
  - **Then:** el sistema marca el pedido como entregado
  - **And:** se registra la confirmación de entrega
- **Escenario:** Primer intento de entrega fallido
  - **Given:** un paquete está en ruta para su primer intento de entrega
  - **When:** el repartidor no logra entregar el paquete
  - **Then:** el sistema registra el intento como fallido
  - **And:** el sistema programa un segundo intento de entrega

### US-011: Segundo intento fallido - regreso a almacén
**Como** sistema de PetMarket, **quiero** regresar el paquete al almacén de origen si el segundo intento de entrega también falla **para** evitar intentos indefinidos y activar el proceso de contacto con el cliente.
- **Escenario:** Segundo intento de entrega exitoso
  - **Given:** el primer intento de entrega de un pedido fue fallido
  - **When:** el repartidor logra entregar el paquete exitosamente en el segundo intento
  - **Then:** el sistema marca el pedido como entregado
  - **And:** se registra la confirmación de entrega
- **Escenario:** Segundo intento de entrega fallido
  - **Given:** el primer intento de entrega de un pedido fue fallido
  - **When:** el repartidor no logra entregar el paquete en el segundo intento
  - **Then:** el paquete regresa al almacén de origen
  - **And:** Atención al cliente debe contactar al cliente

### US-012: Reprogramación o reembolso tras entrega fallida
**Como** cliente, **quiero** que Atención al cliente me contacte para reprogramar mi entrega en caso de que no hayan podido entregar mi pedido en dos intentos, **para** poder decidir si quiero un nuevo intento o prefiero el reembolso.
- **Escenario:** Cliente pide reprogramar la entrega
  - **Given:** un paquete regresó al almacén tras dos intentos fallidos
  - **When:** Atención al cliente contacta al cliente y este acepta reprogramar
  - **Then:** el sistema programa otro intento de entrega
  - **And:** notifica la nueva fecha de entrega al cliente
- **Escenario:** Cliente prefiere reembolsar su pedido
  - **Given:** un paquete regresó al almacén tras dos intentos fallidos
  - **When:** Atención al cliente contacta al cliente y este solicita reembolso
  - **Then:** el sistema solicita el reembolso a Pagos
  - **And:** el pedido se marca como cerrado

### US-013: Solicitud de devolución dentro de ventana
**Como** cliente, **quiero** poder solicitar una devolución dentro de los 5 días hábiles posteriores a la entrega, **para** regresar productos que no cumplen con mis expectativas o se encuentran defectuosos.
- **Escenario:** Cliente solicita devolución dentro del plazo aceptado
  - **Given:** el pedido fue entregado hace menos de 5 días hábiles
  - **When:** el cliente solicita una devolución
  - **Then:** el sistema registra la solicitud
  - **And:** la envía a Atención al cliente para su revisión
- **Escenario:** Cliente solicita devolución fuera del plazo
  - **Given:** el pedido fue entregado hace más de 5 días hábiles
  - **When:** el cliente intenta solicitar una devolución
  - **Then:** el sistema rechaza la solicitud
  - **And:** informa al cliente que la ventana para devoluciones ha terminado

### US-014: Autorización y confirmación de devolución
**Como** Atención al cliente y personal de Almacén, **quiero** autorizar la solicitud de devolución y confirmar la entrega física del producto, **para** garantizar que el reembolso solo se libere cuando el producto haya sido devuelto.
- **Escenario:** Atención al cliente autoriza la devolución
  - **Given:** existe una solicitud de devolución dentro del plazo permitido
  - **When:** Atención al cliente revisa y autoriza la solicitud
  - **Then:** el sistema le indica al cliente cómo regresar el producto
  - **And:** queda pendiente la recepción física en almacén
- **Escenario:** Atención al cliente rechaza la devolución
  - **Given:** existe una solicitud de devolución dentro del plazo permitido
  - **When:** Atención al cliente revisa y rechaza la solicitud
  - **Then:** el sistema informa al cliente el motivo del rechazo
  - **And:** el pedido no se marca para reembolso
- **Escenario:** Almacén confirma recepción del producto devuelto
  - **Given:** una devolución fue autorizada por Atención al cliente
  - **When:** Almacén confirma la recepción del producto
  - **Then:** el sistema libera la solicitud de reembolso a Pagos

### US-015: Reembolso tras confirmación de almacén
**Como** área de Pagos, **quiero** procesar el reembolso una vez que Almacén confirme la recepción del producto devuelto **para** completar el proceso de devolución y cerrar el pedido correctamente.
- **Escenario:** Reembolso procesado tras confirmación de Almacén
  - **Given:** Almacén confirmó la recepción de un producto devuelto
  - **When:** Pagos procesa el reembolso
  - **Then:** el sistema notifica al cliente que el reembolso fue realizado
  - **And:** cierra el pedido correspondiente

### US-016: Indicador de discrepancia de inventario
**Como** Gerencia de Operaciones, **quiero** contar con un indicador que muestre la discrepancia entre el inventario mostrado en el sitio web y la existencia real **para** dar seguimiento a la meta de mantener un error menor al 2% y priorizar acciones correctivas necesarias.
- **Escenario:** Generación del indicador de discrepancia
  - **Given:** existen registros de inventario web e inventario físico por almacén
  - **When:** Gerencia de Operaciones consulta el reporte de discrepancia
  - **Then:** el sistema muestra el porcentaje de discrepancia por producto y por almacén
  - **And:** señala si el porcentaje supera el umbral objetivo de 2%
- **Escenario:** Discrepancia dentro del umbral aceptable
  - **Given:** el reporte de discrepancia de inventario fue generado
  - **When:** la discrepancia total es menor al 2%
  - **Then:** el sistema marca el indicador como dentro de la meta

## 8. Proceso BPMN (docs/fuentes/3_BPMN_PetMarket.pdf)

### Participantes (Swimlanes)
1. **Cliente**
2. **Sistema PetMarket**
3. **Pagos**
4. **Almacén Norte / Sur**
5. **Paquetería / Reparto**
6. **Atención al Cliente**

### Flujo Principal
1. **Reserva de inventario (15 min)** - Cliente inicia checkout → Sistema reserva stock en almacén(es)
2. **Reintentos de pago (máx. 3)** - Sistema valida pago → Si rechazado, permite reintento → 3 fallos = cancelación automática
3. **División de pedidos** - Sistema asigna líneas a almacenes → Crea un solo número de pedido con dos rastreos → Un solo costo de envío
4. **Cancelación** - Antes de preparación: cliente cancela directo → Durante/después: requiere autorización Atención al cliente
5. **Preparación y empaque** - Almacén recibe sub-pedido → Picking → Empaque → Notifica listo
6. **Envío** - Genera guía por almacén → Paquetería recoge → En tránsito
7. **Entrega** - Primer intento → Si exitoso: ENTREGADO → Si fallido: programa segundo
8. **Segundo intento** - Si exitoso: ENTREGADO → Si fallido: paquete regresa a almacén → Atención al cliente contacta
9. **Devolución** - Cliente solicita (≤5 días hábiles) → Atención al cliente autoriza/rechaza → Si autoriza: cliente envía → Almacén confirma recepción → Pagos reembolsa → Pedido cerrado

### Gateways (Decisiones)
- **Gateway 1:** ¿Pago aprobado? → Sí: Confirmar pedido / No: ¿Reintentos < 3? → Sí: Reintentar / No: Cancelar
- **Gateway 2:** ¿Stock suficiente en almacén? → Sí: Reservar / No: StockInsuficienteEvent → Cancelar línea
- **Gateway 3:** ¿Pedido dividido? → Sí: Múltiples surtidos / No: Un surtido
- **Gateway 4:** ¿Cancelación antes de preparación? → Sí: Cancelar directo / No: Requerir autorización Atención al cliente
- **Gateway 5:** ¿Primer intento exitoso? → Sí: ENTREGADO / No: Programar segundo intento
- **Gateway 6:** ¿Segundo intento exitoso? → Sí: ENTREGADO / No: ENTREGA_FALLIDA → Regresar a almacén
- **Gateway 7:** ¿Devolución dentro de 5 días hábiles? → Sí: Procesar / No: Rechazar
- **Gateway 8:** ¿Atención al cliente autoriza devolución? → Sí: Indicaciones al cliente / No: Informar rechazo
- **Gateway 9:** ¿Almacén confirma recepción? → Sí: Reembolso / No: Esperar

### Data Objects (Objetos de Datos)
- Carrito de compra
- Reserva de inventario (15 min)
- Pedido (número único)
- Surtido(s) por almacén
- Pago (estado, reintentos)
- Guía(s) de envío
- Intento(s) de entrega
- Solicitud de devolución
- Autorización de devolución
- Confirmación recepción almacén
- Reembolso

## 9. Stakeholders
| Stakeholder | Rol / Interés |
|-------------|---------------|
| Cliente | Compra productos, da seguimiento a su pedido, solicita cancelaciones o devoluciones. |
| Almacén (Norte / Sur) | Confirma disponibilidad, prepara y empaca pedidos, recibe devoluciones físicas. |
| Pagos | Procesa cargos, reintentos de pago y reembolsos. |
| Paquetería / Reparto | Ejecuta la entrega y reporta intentos fallidos. |
| Atención al cliente | Autoriza cancelaciones tardías, devoluciones y reprogramaciones; resuelve tickets de estatus. |
| Gerencia de Operaciones | Define prioridades de negocio y valida criterios de éxito. |

---

*Documento basado en las fuentes oficiales: docs/fuentes/1_BRD_PetMarket.pdf, docs/fuentes/2_UserStories_PetMarket.pdf, docs/fuentes/3_BPMN_PetMarket.pdf, docs/fuentes/4_Glosario_PetMarket.pdf*