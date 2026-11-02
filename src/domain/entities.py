"""Entidades del dominio PetMarket.

Contiene las entidades que forman parte de los Aggregates:
- LineaPedido: Línea de producto dentro de un Pedido.
- Surtido: Sub-unidad de un Pedido asignada a un Almacén.
- ExistenciaProducto: Stock disponible de un Producto en un Almacén.
- IntentoEntrega: Registro de un intento de entrega de un Envío.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from .value_objects import (
    DireccionEntrega,
    Dinero,
    EstadoSurtido,
    EstadoEnvio,
    Guia,
    MotivoDevolucion,
    Sku,
)


@dataclass
class LineaPedido:
    """Línea de producto dentro de un Pedido.

    Representa una cantidad específica de un SKU a un precio unitario.
    """
    sku: Sku
    cantidad: int
    precio_unitario: Dinero

    def __post_init__(self) -> None:
        if self.cantidad <= 0:
            raise ValueError("La cantidad de la línea de pedido debe ser mayor a 0")
        if not isinstance(self.sku, Sku):
            self.sku = Sku.of(str(self.sku))


@dataclass
class Surtido:
    """Sub-unidad de un Pedido asignada a un Almacén específico.

    Contiene una o más líneas de pedido y evoluciona su estado de forma
    independiente: PENDIENTE -> EN_PREPARACION -> EMPACADO.
    """
    id: UUID
    pedido_id: UUID
    almacen_id: UUID
    lineas: list[LineaPedido] = field(default_factory=list)
    estado: EstadoSurtido = EstadoSurtido.PENDIENTE

    def __post_init__(self) -> None:
        if not self.lineas:
            raise ValueError("Un Surtido debe contener al menos una línea de pedido")

    @property
    def total(self) -> Dinero:
        """Monto total del Surtido (suma de líneas)."""
        return sum(
            (linea.precio_unitario.monto * linea.cantidad for linea in self.lineas),
            Dinero(0, "MXN"),
        )  # type: ignore[return-value]

    def marcar_en_preparacion(self) -> None:
        """Pasa el Surtido al estado EN_PREPARACION."""
        if self.estado != EstadoSurtido.PENDIENTE:
            from .exceptions import TransicionEstadoInvalidaException
            raise TransicionEstadoInvalidaException(
                self.estado.value, EstadoSurtido.EN_PREPARACION.value
            )
        self.estado = EstadoSurtido.EN_PREPARACION

    def marcar_empacado(self) -> None:
        """Pasa el Surtido al estado EMPACADO."""
        if self.estado != EstadoSurtido.EN_PREPARACION:
            from .exceptions import TransicionEstadoInvalidaException
            raise TransicionEstadoInvalidaException(
                self.estado.value, EstadoSurtido.EMPACADO.value
            )
        self.estado = EstadoSurtido.EMPACADO


@dataclass
class ExistenciaProducto:
    """Stock disponible de un Producto en un Almacén específico."""
    producto_id: UUID
    almacen_id: UUID
    sku: Sku
    cantidad_disponible: int
    cantidad_reservada: int = 0

    def __post_init__(self) -> None:
        if self.cantidad_disponible < 0:
            raise ValueError("La cantidad disponible no puede ser negativa")
        if self.cantidad_reservada < 0:
            raise ValueError("La cantidad reservada no puede ser negativa")
        if not isinstance(self.sku, Sku):
            self.sku = Sku.of(str(self.sku))

    @property
    def disponible_para_venta(self) -> int:
        """Cantidad disponible para venta (disponible - reservada)."""
        return self.cantidad_disponible - self.cantidad_reservada

    def reservar(self, cantidad: int) -> None:
        """Reserva `cantidad` unidades del stock disponible.

        # SUPUESTO: La reserva expira a los 15 minutos. Validar con el negocio.
        US-001, US-002
        """
        if cantidad <= 0:
            raise ValueError("La cantidad a reservar debe ser mayor a 0")
        if cantidad > self.disponible_para_venta:
            from .exceptions import StockInsuficienteError
            raise StockInsuficienteError(
                str(self.sku), cantidad, self.disponible_para_venta
            )
        self.cantidad_reservada += cantidad

    def liberar_reserva(self, cantidad: int) -> None:
        """Libera `cantidad` unidades de la reserva."""
        if cantidad <= 0:
            raise ValueError("La cantidad a liberar debe ser mayor a 0")
        if cantidad > self.cantidad_reservada:
            raise ValueError("No se puede liberar más de lo reservado")
        self.cantidad_reservada -= cantidad

    def confirmar_reserva(self, cantidad: int) -> None:
        """Confirma la reserva (descuenta de disponible y libera reserva).

        US-004: Pago aprobado -> confirma la reserva como venta.
        """
        if cantidad <= 0:
            raise ValueError("La cantidad a confirmar debe ser mayor a 0")
        if cantidad > self.cantidad_reservada:
            raise ValueError("No se puede confirmar más de lo reservado")
        self.cantidad_reservada -= cantidad
        self.cantidad_disponible -= cantidad


@dataclass
class IntentoEntrega:
    """Registro de un intento de entrega de un Envío en la dirección del Cliente."""
    id: UUID
    envio_id: UUID
    exitoso: bool
    numero_intento: int
    observaciones: str = ""

    def __post_init__(self) -> None:
        if self.numero_intento <= 0:
            raise ValueError("El número de intento debe ser mayor a 0")


@dataclass
class LineaDevolucion:
    """Línea de devolución: producto y cantidad a devolver."""
    sku: Sku
    cantidad: int

    def __post_init__(self) -> None:
        if self.cantidad <= 0:
            raise ValueError("La cantidad de la línea de devolución debe ser mayor a 0")
        if not isinstance(self.sku, Sku):
            self.sku = Sku.of(str(self.sku))