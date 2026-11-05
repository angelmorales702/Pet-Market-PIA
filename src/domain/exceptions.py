"""Excepciones del Dominio PetMarket.

Excepciones que representan violaciones a las reglas de negocio.
No dependen de FastAPI, SQLAlchemy ni de ningún framework externo.
"""
from __future__ import annotations


class DominioError(Exception):
    """Clase base para todos los errores del dominio PetMarket."""
    pass


class StockInsuficienteError(DominioError):
    """Se intentó comprar más unidades de las disponibles en el inventario."""
    def __init__(self, sku: str, solicitado: int, disponible: int) -> None:
        self.sku = sku
        self.solicitado = solicitado
        self.disponible = disponible
        super().__init__(
            f"Stock insuficiente para SKU '{sku}': solicitado {solicitado}, "
            f"disponible {disponible}"
        )


class PagoRechazadoError(DominioError):
    """El pago fue rechazado por el proveedor de pagos."""
    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__(f"Pago rechazado: {motivo}")


class TransicionEstadoInvalidaException(DominioError):
    """Se intentó realizar una transición de estado no permitida."""
    def __init__(self, estado_actual: str, estado_destino: str) -> None:
        self.estado_actual = estado_actual
        self.estado_destino = estado_destino
        super().__init__(
            f"Transición inválida: no se puede pasar de '{estado_actual}' "
            f"a '{estado_destino}'"
        )


class SurtidoNoEmpacadoError(DominioError):
    """Se intentó acceder a un surtido que aún no está empacado."""
    def __init__(self, surtido_id: str) -> None:
        self.surtido_id = surtido_id
        super().__init__(f"El surtido '{surtido_id}' no está en estado EMPACADO")


class IntentosEntregaAgotadosError(DominioError):
    """Se superó el número máximo de intentos de entrega."""
    def __init__(self, maximos: int) -> None:
        self.maximos = maximos
        super().__init__(
            f"Se alcanzó el máximo de intentos de entrega ({maximos}). "
            f"La entrega se marca como FALLIDA."
        )


class PagoMontoNoCoincideError(DominioError):
    """El monto del pago no coincide con el total del pedido."""
    def __init__(self, pagado: str, total: str) -> None:
        self.pagado = pagado
        self.total = total
        super().__init__(
            f"El monto del pago ({pagado}) no coincide con el total del pedido ({total})"
        )


class ProductoNoEncontradoError(DominioError):
    """No existe un producto con el SKU especificado."""
    def __init__(self, sku: str) -> None:
        self.sku = sku
        super().__init__(f"Producto no encontrado con SKU '{sku}'")


class AlmacenNoEncontradoError(DominioError):
    """No existe el almacén especificado."""
    def __init__(self, almacen_id: str) -> None:
        self.almacen_id = almacen_id
        super().__init__(f"Almacén no encontrado con ID '{almacen_id}'")


class SurtidoNoEncontradoError(DominioError):
    """No existe el surtido especificado dentro del pedido."""
    def __init__(self, surtido_id: str) -> None:
        self.surtido_id = surtido_id
        super().__init__(f"Surtido no encontrado con ID '{surtido_id}'")


class DevolucionNoPermitidaError(DominioError):
    """No se puede solicitar la devolución para el estado actual del pedido."""
    def __init__(self, estado: str) -> None:
        self.estado = estado
        super().__init__(
            f"La devolución no está permitida para un pedido en estado '{estado}'"
        )


class CancelacionNoPermitidaError(DominioError):
    """No se puede cancelar el pedido en su estado actual."""
    def __init__(self, estado: str) -> None:
        self.estado = estado
        super().__init__(
            f"La cancelación no está permitida para un pedido en estado '{estado}'"
        )


class PedidoNoEncontradoError(DominioError):
    """No existe el pedido con el ID especificado."""
    def __init__(self, pedido_id: str) -> None:
        self.pedido_id = pedido_id
        super().__init__(f"Pedido no encontrado con ID '{pedido_id}'")


class DevolucionNoEncontradoError(DominioError):
    """No existe la devolución con el ID especificado."""
    def __init__(self, devolucion_id: str) -> None:
        self.devolucion_id = devolucion_id
        super().__init__(f"Devolución no encontrada con ID '{devolucion_id}'")