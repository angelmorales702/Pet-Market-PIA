"""Tests unitarios del dominio - Pedido y State Machine.

Cada test cita la User Story que cubre según docs/fuentes.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.aggregates import Pedido
from src.domain.entities import LineaPedido
from src.domain.exceptions import (
    CancelacionNoPermitidaError,
    TransicionEstadoInvalidaException,
)
from src.domain.state_machine import EstadoPedido
from src.domain.value_objects import Dinero, DireccionEntrega, Sku


@pytest.fixture
def direccion() -> DireccionEntrega:
    return DireccionEntrega(
        calle="Av Reforma",
        numero="123",
        colonia="Centro",
        ciudad="Monterrey",
        codigo_postal="64000",
    )


@pytest.fixture
def linea_pedido() -> LineaPedido:
    sku = Sku.of("SKU-00001")
    return LineaPedido(
        sku=sku,
        cantidad=2,
        precio_unitario=Dinero(100, "MXN"),
    )


def test_pedido_creado_estado_creado(linea_pedido, direccion) -> None:
    """US-004: Pedido creado tras pago exitoso."""
    pedido = Pedido.crear(
        cliente_id=uuid4(),
        lineas=[linea_pedido],
        direccion_entrega=direccion,
    )
    assert pedido.estado == EstadoPedido.CREADO
    assert len(pedido.domain_events) == 1


def test_pedido_transicion_a_pagado(linea_pedido, direccion) -> None:
    """US-004: Compra confirmada tras pago exitoso."""
    from uuid import uuid4

    from src.domain.entities import Surtido

    pedido = Pedido.crear(
        cliente_id=uuid4(),
        lineas=[linea_pedido],
        direccion_entrega=direccion,
    )
    # Asignar surtidos para transicionar a PENDIENTE_PAGO
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=uuid4(),
        lineas=[linea_pedido],
    )
    pedido.asignar_surtidos([surtido])
    assert pedido.estado == EstadoPedido.PENDIENTE_PAGO

    monto = Dinero(200, "MXN")
    pedido.marcar_pagado(monto)
    assert pedido.estado == EstadoPedido.PAGADO


def test_pedido_cancelar_cliente_antes_de_preparacion(linea_pedido, direccion) -> None:
    """US-008: Cancelación antes de preparación sin penalización."""
    from uuid import uuid4

    from src.domain.entities import Surtido

    pedido = Pedido.crear(
        cliente_id=uuid4(),
        lineas=[linea_pedido],
        direccion_entrega=direccion,
    )
    # Asignar surtidos
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=uuid4(),
        lineas=[linea_pedido],
    )
    pedido.asignar_surtidos([surtido])

    monto = Dinero(200, "MXN")
    pedido.marcar_pagado(monto)
    assert pedido.puede_cancelar_cliente() is True
    pedido.cancelar("cambio de opinión")
    assert pedido.estado == EstadoPedido.CANCELADO


def test_pedido_no_cancelable_despues_de_enviado(linea_pedido, direccion) -> None:
    """US-009: Cancelación tardía requiere autorización."""
    from uuid import uuid4

    from src.domain.entities import Surtido
    from src.domain.value_objects import Guia

    pedido = Pedido.crear(
        cliente_id=uuid4(),
        lineas=[linea_pedido],
        direccion_entrega=direccion,
    )
    # Asignar surtidos
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=uuid4(),
        lineas=[linea_pedido],
    )
    pedido.asignar_surtidos([surtido])

    monto = Dinero(200, "MXN")
    pedido.marcar_pagado(monto)
    pedido.iniciar_preparacion()
    # confirmar_empaque llama internamente a marcar_empacado
    pedido.confirmar_empaque(almacen_id=surtido.almacen_id)
    pedido.marcar_enviado(Guia("TRACK-123"))
    assert pedido.estado == EstadoPedido.ENVIADO
    with pytest.raises(CancelacionNoPermitidaError):
        pedido.cancelar("quiero cancelar")


def test_pedido_transicion_invalida() -> None:
    """State Machine: transición inválida lanza excepción."""
    from src.domain.state_machine import transitar
    with pytest.raises(TransicionEstadoInvalidaException):
        transitar(EstadoPedido.CREADO, EstadoPedido.ENVIADO)


def test_pedido_total_calculado(linea_pedido, direccion) -> None:
    """US-004: Total del pedido se calcula correctamente."""
    pedido = Pedido.crear(
        cliente_id=uuid4(),
        lineas=[linea_pedido],
        direccion_entrega=direccion,
    )
    assert pedido.total == Dinero(200, "MXN")


def test_pedido_reintentos_pago_tres_veces() -> None:
    """US-003: Máximo 3 reintentos de pago antes de cancelar."""
    from src.domain.aggregates import Pedido
    from src.domain.entities import LineaPedido
    from src.domain.value_objects import Dinero, DireccionEntrega, Sku

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00002"), 1, Dinero(100, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    Dinero(100, "MXN")

    pedido.marcar_pago_rechazado("Tarjeta rechazada")
    pedido.marcar_pago_rechazado("Tarjeta rechazada")
    pedido.marcar_pago_rechazado("Tarjeta rechazada")

    assert pedido.estado == EstadoPedido.CANCELADO
    assert pedido.reintentos_pago == 3