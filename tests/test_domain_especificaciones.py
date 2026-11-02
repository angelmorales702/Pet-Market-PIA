"""Tests unitarios - Specifications.

US-008, US-009, US-013, US-014
"""
from __future__ import annotations

from uuid import uuid4

from src.domain.aggregates import Almacen, Pedido
from src.domain.entities import LineaPedido
from src.domain.specifications import (
    PedidoCancelableSpec,
    PedidoEntregadoSpec,
    PagoAprobableSpec,
)
from src.domain.state_machine import EstadoPedido
from src.domain.value_objects import DireccionEntrega, Dinero, Sku


def test_pedido_cancelable_spec_estado_pagado() -> None:
    """US-008: Pedido en estado PAGADO es cancelable por cliente."""
    from uuid import uuid4
    from src.domain.entities import Surtido

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00007"), 1, Dinero(100, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    # Asignar surtidos
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=uuid4(),
        lineas=[linea],
    )
    pedido.asignar_surtidos([surtido])
    pedido.marcar_pagado(Dinero(100, "MXN"))

    spec = PedidoCancelableSpec()
    assert spec.is_satisfied_by(pedido) is True


def test_pedido_cancelable_spec_estado_enviado() -> None:
    """US-009: Pedido en estado ENVIADO no es cancelable por cliente."""
    from uuid import uuid4
    from src.domain.entities import Surtido
    from src.domain.value_objects import Guia

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00008"), 1, Dinero(100, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    # Asignar surtidos
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=uuid4(),
        lineas=[linea],
    )
    pedido.asignar_surtidos([surtido])
    pedido.marcar_pagado(Dinero(100, "MXN"))
    pedido.iniciar_preparacion()
    # confirmar_empaque llama internamente a marcar_empacado
    pedido.confirmar_empaque(almacen_id=surtido.almacen_id)
    pedido.marcar_enviado(Guia("TRACK-999"))

    spec = PedidoCancelableSpec()
    assert spec.is_satisfied_by(pedido) is False


def test_pago_aprobable_spec_monto_coincide() -> None:
    """US-004: Pago aprobado cuando monto coincide con total."""
    from uuid import uuid4
    from src.domain.entities import Surtido

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00009"), 2, Dinero(50, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    # Asignar surtidos
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=uuid4(),
        lineas=[linea],
    )
    pedido.asignar_surtidos([surtido])

    spec = PagoAprobableSpec(Dinero(100, "MXN"))
    assert spec.is_satisfied_by(pedido) is True


def test_pago_aprobable_spec_monto_diferente() -> None:
    """US-004: Pago rechazado cuando monto no coincide."""
    from uuid import uuid4
    from src.domain.entities import Surtido

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00010"), 2, Dinero(50, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    # Asignar surtidos
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=uuid4(),
        lineas=[linea],
    )
    pedido.asignar_surtidos([surtido])

    spec = PagoAprobableSpec(Dinero(90, "MXN"))
    assert spec.is_satisfied_by(pedido) is False