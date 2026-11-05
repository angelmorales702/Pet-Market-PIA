# Contrato de Errores de la API

PetMarket API expone un contrato de errores explícito con códigos HTTP específicos.

## Principios

- **404**: Recurso inexistente. Ej: pedido no encontrado, devolución no encontrada, almacén no encontrado.
- **409**: Conflicto de estado o de negocio. Ej: transición de estado inválida, cancelación no permitida, stock insuficiente, devolución no permitida, monto de pago no coincide.
- **422**: Validación de datos inválidos. Ej: formato de SKU inválido, campos faltantes, código postal inválido, datos del pedido inválidos.
- **500**: Error interno del servidor. **NO debe ocurrir en producción**. Todas las excepciones conocidas se traducen a 404/409/422. Las inesperadas se loguean y se mapean a 500.

## Mapeo de excepciones

### 404 Not Found - Recursos no encontrados

| Excepción del dominio | Código HTTP | Código error | Mensaje |
|---|---|---|---|
| `PedidoNoEncontradoError` | 404 | `PEDIDO_NO_ENCONTRADO` | Pedido {id} no encontrado |
| `DevolucionNoEncontradoError` | 404 | `DEVOLUCION_NO_ENCONTRADO` | Devolución {id} no encontrada |
| `AlmacenNoEncontradoError` | 404 | `ALMACEN_NO_ENCONTRADO` | Almacén {id} no encontrado |
| `SurtidoNoEncontradoError` | 404 | `SURTIDO_NO_ENCONTRADO` | Surtido {id} no encontrado |
| `ProductoNoEncontradoError` | 404 | `PRODUCTO_NO_ENCONTRADO` | Producto con SKU '{sku}' no encontrado |

### 409 Conflict - Errores de negocio

| Excepción del dominio | Código HTTP | Código error | Mensaje |
|---|---|---|---|
| `TransicionEstadoInvalidaException` | 409 | `ESTADO_INVALIDO` | Transición de estado inválida: {estado_actual} → {estado_destino} |
| `CancelacionNoPermitidaError` | 409 | `CANCELACION_NO_PERMITIDA` | No se puede cancelar un pedido en estado {estado} |
| `DevolucionNoPermitidaError` | 409 | `DEVOLUCION_NO_PERMITIDA` | La devolución no está permitida para un pedido en estado {estado} |
| `StockInsuficienteError` | 409 | `STOCK_INSUFICIENTE` | Stock insuficiente para SKU '{sku}': solicitado {solicitado}, disponible {disponible} |

### 422 Unprocessable Entity - Validación

| Error | Código HTTP | Código error | Mensaje |
|---|---|---|---|
| SKU inválido | 422 | `SKU_INVALIDO` | Formato de SKU inválido |
| Validación Pydantic | 422 | `DATOS_INVALIDOS` | Error de validación de datos |

## Formato de respuesta

Todas las respuestas de error siguen el formato:

```json
{
  "detail": {
    "codigo": "CODIGO_ERROR",
    "mensaje": "Descripción del error"
  }
}
```

## Ejemplos

### 404 Recurso no encontrado

#### Pedido no encontrado
```json
{
  "detail": {
    "codigo": "PEDIDO_NO_ENCONTRADO",
    "mensaje": "Pedido 12345678-1234-1234-1234-123456789012 no encontrado"
  }
}
```

#### Almacén no encontrado
```json
{
  "detail": {
    "codigo": "ALMACEN_NO_ENCONTRADO",
    "mensaje": "Almacén 12345678-1234-1234-1234-123456789012 no encontrado"
  }
}
```

#### Producto no encontrado
```json
{
  "detail": {
    "codigo": "PRODUCTO_NO_ENCONTRADO",
    "mensaje": "Producto con SKU 'SKU-99999' no encontrado"
  }
}
```

#### Devolución no encontrada
```json
{
  "detail": {
    "codigo": "DEVOLUCION_NO_ENCONTRADO",
    "mensaje": "Devolución 12345678-1234-1234-1234-123456789012 no encontrada"
  }
}
```

#### Surtido no encontrado
```json
{
  "detail": {
    "codigo": "SURTIDO_NO_ENCONTRADO",
    "mensaje": "Surtido 12345678-1234-1234-1234-123456789012 no encontrado"
  }
}
```

### 409 Conflicto de estado

#### Transición de estado inválida
```json
{
  "detail": {
    "codigo": "ESTADO_INVALIDO",
    "mensaje": "Transición de estado inválida: PENDIENTE_PAGO → EN_PREPARACION"
  }
}
```

#### Cancelación no permitida
```json
{
  "detail": {
    "codigo": "CANCELACION_NO_PERMITIDA",
    "mensaje": "No se puede cancelar un pedido en estado PAGADO"
  }
}
```

#### Devolución no permitida
```json
{
  "detail": {
    "codigo": "DEVOLUCION_NO_PERMITIDA",
    "mensaje": "La devolución no está permitida para un pedido en estado PAGADO"
  }
}
```

#### Stock insuficiente
```json
{
  "detail": {
    "codigo": "STOCK_INSUFICIENTE",
    "mensaje": "Stock insuficiente para SKU 'SKU-00001': solicitado 10, disponible 5"
  }
}
```

### 422 Validación

#### SKU inválido
```json
{
  "detail": {
    "codigo": "SKU_INVALIDO",
    "mensaje": "Formato de SKU inválido: SKU-ABC. El formato debe ser SKU-XXXXX (5 dígitos)"
  }
}
```

#### Validación de campo
```json
{
  "detail": {
    "codigo": "DATOS_INVALIDOS",
    "mensaje": "Código postal debe ser numérico"
  }
}
```

## Manejo de excepciones en el código

Según el principio de arquitectura, los endpoints deben lanzar excepciones de dominio en vez de `ValueError` o `HTTPException` sin mapear. Los manejadores de excepciones de FastAPI traducen estas a respuestas HTTP.

### Reglas de mapeo

| Error "no encontrado" | Excepciones de dominio  | Código HTTP |
|---|---|---|
| Pedido no encontrado | `PedidoNoEncontradoError` | 404 |
| Devolución no encontrada | `DevolucionNoEncontradoError` | 404 |
| Almacén no encontrado | `AlmacenNoEncontradoError` | 404 |
| Surtido no encontrado | `SurtidoNoEncontradoError` | 404 |
| Producto no encontrado | `ProductoNoEncontradoError` | 404 |

| Error de negocio | Excepciones de dominio | Código HTTP |
|---|---|---|
| Transición de estado inválida | `TransicionEstadoInvalidaException` | 409 |
| Cancelación no permitida | `CancelacionNoPermitidaError` | 409 |
| Devolución no permitida | `DevolucionNoPermitidaError` | 409 |
| Stock insuficiente | `StockInsuficienteError` | 409 |

### Endpoints con HTTPException (legacy)

Algunos endpoints aún usan `HTTPException` directamente para casos específicos que no representan errores de dominio (ej: producto inactivo). El handler `handle_http_exception` asegura que sigan el formato `{"detail": {"codigo": "...", "mensaje": "..."}}` sin exponer 500.

Ejemplo correcto:
```python
# En el caso de uso
def ejecutar(self, pedido_id: UUID, ...) -> Pedido:
    pedido = uow.pedidos.obtener_por_id(pedido_id)
    if not pedido:
        raise PedidoNoEncontradoError(str(pedido_id))  # Excepción de dominio
    ...

# En el endpoint
async def cancelar_pedido(pedido_id: UUID, ...):
    use_case = CancelarPedidoUseCase(uow, publisher)
    pedido = use_case.ejecutar(pedido_id, motivo, autorizado)
    return PedidoResponse.from_domain(pedido)
```

El manejador global de excepciones traduce `PedidoNoEncontradoError` → 404 con código `PEDIDO_NO_ENCONTRADO`.