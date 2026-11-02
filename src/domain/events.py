"""Domain Events del PetMarket.

Los Domain Events permiten desacoplar los efectos secundarios (notificaciones,
actualización de stocks) de los cambios de estado de los agregados.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DomainEvent:
    """Clase base para todos los Domain Events del sistema."""
    pass


@dataclass(frozen=True)
class PedidoCreadoEvent(DomainEvent):
    """Se emite cuando un nuevo pedido es creado exitosamente."""
    pedido_id: UUID
    cliente_id: UUID


@dataclass(frozen=True)
class PagoAprobadoEvent(DomainEvent):
    """Se emite cuando un pago es aprobado y el pedido avanza a PAGADO."""
    pedido_id: UUID
    monto: str
    moneda: str


@dataclass(frozen=True)
class PagoRechazadoEvent(DomainEvent):
    """Se emite cuando un pago es rechazado."""
    pedido_id: UUID
    monto: str
    moneda: str
    motivo: str


@dataclass(frozen=True)
class SurtidoEmpacadoEvent(DomainEvent):
    """Se emite cuando un surtido específico es marcado como EMPACADO."""
    pedido_id: UUID
    surtido_id: UUID


@dataclass(frozen=True)
class PedidoEmpacadoEvent(DomainEvent):
    """Se emite cuando todos los surtidos del pedido están EMPACADO."""
    pedido_id: UUID


@dataclass(frozen=True)
class PedidoEnviadoEvent(DomainEvent):
    """Se emite cuando el pedido es despachado y recibe su guía."""
    pedido_id: UUID
    guia: str


@dataclass(frozen=True)
class IntentoEntregaRegistradoEvent(DomainEvent):
    """Se emite cuando se registra un intento de entrega."""
    pedido_id: UUID
    exitoso: bool
    numero_intentos: int


@dataclass(frozen=True)
class PedidoEntregadoEvent(DomainEvent):
    """Se emite cuando la entrega es confirmada exitosamente."""
    pedido_id: UUID


@dataclass(frozen=True)
class PedidoCanceladoEvent(DomainEvent):
    """Se emite cuando el pedido es cancelado."""
    pedido_id: UUID


@dataclass(frozen=True)
class DevolucionSolicitadaEvent(DomainEvent):
    """Se emite cuando se solicita una devolución para un pedido entregado."""
    pedido_id: UUID
    devolucion_id: UUID
    motivo: str