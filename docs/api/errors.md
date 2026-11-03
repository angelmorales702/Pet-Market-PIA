# Contrato de Errores de la API

PetMarket API expone un contrato de errores explícito con códigos HTTP específicos.

## Principios

- **404**: Recurso inexistente. Ej: producto no encontrado, pedido no encontrado, almacén no encontrado.
- **409**: Conflicto de estado o de negocio. Ej: transición de estado inválida, cancelación no permitida, stock insuficiente, devolución no permitida, monto de pago no coincide.
- **422**: Validación de datos inválidos. Ej: formato de SKU inválido, campos faltantes, código postal inválido, datos del pedido inválidos.
- **500**: Error interno del servidor. **NO debe ocurrir en producción**. Todas las excepciones conocidas se traducen a 404/409/422. Las inesperadas se loguean y se mapean a 500.

## Mapeo de excepciones

| Excepción del dominio | HTTP | Código |
|---|---|---|
| `TransicionEstadoInvalidaException` | 409 | `ESTADO_INVALIDO` |
| `CancelacionNoPermitidaError` | 409 | `CANCELACION_NO_PERMITIDA` |
| `DevolucionNoPermitidaError` | 409 | `DEVOLUCION_NO_PERMITIDA` |
| `StockInsuficienteError` | 409 | `STOCK_INSUFICIENTE` |
| `PagoMontoNoCoincideError` | 409 | `ESTADO_INVALIDO` |
| `ProductoNoEncontradoError` / `ValueError` (SKU) | 422 | `SKU_INVALIDO` / `DATOS_INVALIDOS` |
| Recurso no encontrado por repositorio | 404 | `NO_ENCONTRADO` |
| Validación Pydantic / FastAPI | 422 | `DATOS_INVALIDOS` |

## Ejemplos

### 404 Recurso no encontrado
```json
{
  "codigo": "PRODUCTO_NO_ENCONTRADO",
  "mensaje": "Producto con SKU SKU-99999 no encontrado"
}
```

### 409 Conflicto de estado
```json
{
  "codigo": "ESTADO_INVALIDO",
  "mensaje": "Transición de estado inválida: PENDIENTE_PAGO → EN_PREPARACION"
}
```

### 409 Stock insuficiente
```json
{
  "codigo": "STOCK_INSUFICIENTE",
  "mensaje": "Stock insuficiente para SKU 'SKU-00001': solicitado 10, disponible 5"
}
```

### 422 SKU inválido
```json
{
  "codigo": "SKU_INVALIDO",
  "mensaje": "Formato de SKU inválido: SKU-ABC. El formato debe ser SKU-XXXXX (5 dígitos)"
}
```
