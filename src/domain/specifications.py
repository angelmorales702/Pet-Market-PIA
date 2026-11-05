"""Patrón Specification para reglas de negocio combinables.

Las Specifications encapsulan reglas de validación que se pueden combinar
con operadores lógicos (and, or, not). Se usan en la capa de aplicación
para validar precondiciones antes de ejecutar casos de uso.

Alineados con docs/fuentes/ADR.md (ADR-004) y User Stories.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from .aggregates import Almacen, Pedido, Producto
from .entities import ExistenciaProducto
from .state_machine import EstadoPedido
from .value_objects import Dinero, DireccionEntrega

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    """Clase base abstracta para Specification."""

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Evalúa si el candidato satisface la especificación."""
        pass

    def and_(self, other: "Specification[T]") -> "AndSpecification[T]":
        return AndSpecification(self, other)

    def or_(self, other: "Specification[T]") -> "OrSpecification[T]":
        return OrSpecification(self, other)

    def not_(self) -> "NotSpecification[T]":
        return NotSpecification(self)


class AndSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)


class OrSpecification(Specification[T]):
    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)


class NotSpecification(Specification[T]):
    def __init__(self, spec: Specification[T]) -> None:
        self.spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.spec.is_satisfied_by(candidate)


# ============================================================================
# SPECIFICATIONS PARA PRODUCTO
# ============================================================================

class ProductoDisponibleSpec(Specification[Producto]):
    """Verifica que un producto esté activo y disponible para la venta.

    US-001, US-002: Producto disponible para reserva durante checkout.
    """
    def __init__(self, almacen: Almacen, cantidad_requerida: int = 1) -> None:
        self.almacen = almacen
        self.cantidad_requerida = cantidad_requerida

    def is_satisfied_by(self, producto: Producto) -> bool:
        if not producto.activo:
            return False
        ex = self.almacen.obtener_existencia(producto.sku)
        if not ex:
            return False
        return ex.disponible_para_venta >= self.cantidad_requerida


class ProductoActivoSpec(Specification[Producto]):
    """Verifica que el producto esté activo en catálogo."""
    def is_satisfied_by(self, producto: Producto) -> bool:
        return producto.activo


# ============================================================================
# SPECIFICATIONS PARA PEDIDO
# ============================================================================

class PedidoCancelableSpec(Specification[Pedido]):
    """Verifica que el pedido pueda ser cancelado por el cliente.

    US-008: Cancelación antes de preparación sin penalización.
    US-009: Cancelación tardía requiere autorización (no cubierta aquí).
    """
    def is_satisfied_by(self, pedido: Pedido) -> bool:
        return pedido.puede_cancelar_cliente()


class PedidoPagadoSpec(Specification[Pedido]):
    """Verifica que el pedido esté en estado PAGADO."""
    def is_satisfied_by(self, pedido: Pedido) -> bool:
        return pedido.estado == EstadoPedido.PAGADO


class PedidoEntregadoSpec(Specification[Pedido]):
    """Verifica que el pedido esté en estado ENTREGADO."""
    def is_satisfied_by(self, pedido: Pedido) -> bool:
        return pedido.estado == EstadoPedido.ENTREGADO


class PedidoEnPreparacionSpec(Specification[Pedido]):
    """Verifica que el pedido esté en preparación o posterior."""
    def is_satisfied_by(self, pedido: Pedido) -> bool:
        estados_post_preparacion = {
            EstadoPedido.EN_PREPARACION,
            EstadoPedido.EMPACADO,
            EstadoPedido.ENVIADO,
            EstadoPedido.ENTREGADO,
            EstadoPedido.ENTREGA_FALLIDA,
        }
        return pedido.estado in estados_post_preparacion


class PedidoConStockSuficienteSpec(Specification[Pedido]):
    """Verifica que todos los productos del pedido tengan stock en sus almacenes asignados.

    US-006: Pedido con productos en dos almacenes.
    """
    def is_satisfied_by(self, pedido: Pedido) -> bool:
        for surtido in pedido.surtidos:
            for linea in surtido.lineas:
                # La verificación real se hace en Almacen al reservar
                pass
        return True  # Placeholder: la verificación real es en Almacen.reservar()


# ============================================================================
# SPECIFICATIONS PARA PAGO
# ============================================================================

class PagoAprobableSpec(Specification[Pedido]):
    """Verifica que el monto del pago coincida con el total del pedido.

    US-004: Compra confirmada tras pago exitoso.
    """
    def __init__(self, monto_pagado: Dinero) -> None:
        self.monto_pagado = monto_pagado

    def is_satisfied_by(self, pedido: Pedido) -> bool:
        return self.monto_pagado == pedido.total


class PagoMontoValidoSpec(Specification[Dinero]):
    """Verifica que el monto sea positivo."""
    def is_satisfied_by(self, monto: Dinero) -> bool:
        return monto.monto > 0


# ============================================================================
# SPECIFICATIONS PARA DIRECCIÓN
# ============================================================================

class DireccionValidaSpec(Specification[DireccionEntrega]):
    """Verifica que la dirección cumpla criterios mínimos.

    US-006: Validación de domicilio en checkout.
    """
    def is_satisfied_by(self, direccion: DireccionEntrega) -> bool:
        # La validación de formato ya está en __post_init__ del VO
        # Aquí se podrían añadir validaciones de negocio (cobertura, zona, etc.)
        # # SUPUESTO: Validar cobertura por código postal. Validar con el negocio.
        return True


# ============================================================================
# SPECIFICATIONS PARA DEVOLUCIÓN
# ============================================================================

class DevolucionDentroDeVentanaSpec(Specification[Pedido]):
    """Verifica que el pedido esté dentro de la ventana de 5 días hábiles para devolución.

    US-013: Ventana de devolución de 5 días hábiles.
    """
    def __init__(self, fecha_entrega, calendario=None) -> None:
        self.fecha_entrega = fecha_entrega
        self._calendario = calendario

    def is_satisfied_by(self, pedido: Pedido) -> bool:
        if pedido.estado != EstadoPedido.ENTREGADO:
            return False
        # Delegar a Devolucion.esta_dentro_ventana
        from .aggregates import Devolucion
        dev = Devolucion(
            id=UUID(int=0),  # dummy
            pedido_id=pedido.id,
            lineas=[],
            motivo=None,  # type: ignore
        )
        return dev.esta_dentro_ventana(self.fecha_entrega, calendario=self._calendario)


class DevolucionAprobadaSpec(Specification):
    """Verifica que la devolución haya sido autorizada por Atención al cliente.

    US-014: Atención al cliente autoriza la devolución.
    """
    def is_satisfied_by(self, devolucion) -> bool:
        from .value_objects import EstadoDevolucion
        return devolucion.estado == EstadoDevolucion.APROBADA


# ============================================================================
# SPECIFICATIONS PARA ALMACÉN / INVENTARIO
# ============================================================================

class StockSuficienteSpec(Specification[ExistenciaProducto]):
    """Verifica que la existencia tenga stock suficiente para la cantidad requerida."""
    def __init__(self, cantidad_requerida: int) -> None:
        self.cantidad_requerida = cantidad_requerida

    def is_satisfied_by(self, existencia: ExistenciaProducto) -> bool:
        return existencia.disponible_para_venta >= self.cantidad_requerida


# ============================================================================
# SPECIFICATIONS COMPUESTAS (EJEMPLOS DE USO)
# ============================================================================

@dataclass
class CheckoutValidoSpec:
    """Especificación compuesta para validar un checkout completo.

    US-001, US-002, US-004, US-006
    """
    producto_spec: ProductoDisponibleSpec
    direccion_spec: DireccionValidaSpec
    pago_spec: PagoAprobableSpec

    def is_satisfied_by(
        self,
        producto: Producto,
        direccion: DireccionEntrega,
        pedido: Pedido,
        monto_pagado: Dinero,
    ) -> bool:
        return (
            self.producto_spec.is_satisfied_by(producto)
            and self.direccion_spec.is_satisfied_by(direccion)
            and self.pago_spec.is_satisfied_by(pedido)
        )


# Especificaciones predefinidas para uso común
ProductoDisponible = ProductoDisponibleSpec
PedidoCancelable = PedidoCancelableSpec
PagoAprobable = PagoAprobableSpec
DireccionValida = DireccionValidaSpec
DevolucionDentroDeVentana = DevolucionDentroDeVentanaSpec
StockSuficiente = StockSuficienteSpec