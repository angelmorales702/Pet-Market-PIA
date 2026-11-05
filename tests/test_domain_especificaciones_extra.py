"""Tests unitarios extra - Specifications.

US-001, US-002, US-008, US-009, US-013, US-014
"""
from __future__ import annotations

from uuid import uuid4

from src.domain.aggregates import Almacen, Pedido
from src.domain.entities import LineaPedido
from src.domain.specifications import (
    PagoAprobableSpec,
    PedidoEntregadoSpec,
    PedidoPagadoSpec,
    ProductoActivoSpec,
    ProductoDisponibleSpec,
    StockSuficienteSpec,
)
from src.domain.state_machine import EstadoPedido
from src.domain.value_objects import Dinero, DireccionEntrega, Sku


def test_producto_activo_spec() -> None:
    """US-001: Producto activo."""
    from src.domain.aggregates import Producto

    producto_activo = Producto.crear(
        Sku.of("SKU-00001"), "Producto", "Desc", Dinero(100, "MXN"), "Alimentos"
    )
    producto_inactivo = Producto.crear(
        Sku.of("SKU-00002"), "Producto", "Desc", Dinero(100, "MXN"), "Alimentos"
    )
    producto_inactivo.desactivar()

    spec = ProductoActivoSpec()
    assert spec.is_satisfied_by(producto_activo) is True
    assert spec.is_satisfied_by(producto_inactivo) is False


def test_producto_disponible_spec_con_stock() -> None:
    """US-001, US-002: Producto disponible con stock en almacén."""
    from src.domain.aggregates import Producto

    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00003")
    almacen.agregar_existencia(producto_id, sku, 10)

    producto = Producto.crear(sku, "Producto", "Desc", Dinero(100, "MXN"), "Alimentos")

    spec = ProductoDisponibleSpec(almacen, 5)
    assert spec.is_satisfied_by(producto) is True


def test_producto_disponible_spec_sin_stock() -> None:
    """US-005: Producto no disponible sin stock."""
    from src.domain.aggregates import Producto

    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00004")
    almacen.agregar_existencia(producto_id, sku, 2)

    producto = Producto.crear(sku, "Producto", "Desc", Dinero(100, "MXN"), "Alimentos")

    spec = ProductoDisponibleSpec(almacen, 5)
    assert spec.is_satisfied_by(producto) is False


def test_pedido_pagado_spec() -> None:
    """US-008: Pedido en estado PAGADO."""
    from uuid import uuid4

    from src.domain.entities import Surtido

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00005"), 1, Dinero(100, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    surtido = Surtido(id=uuid4(), pedido_id=pedido.id, almacen_id=uuid4(), lineas=[linea])
    pedido.asignar_surtidos([surtido])
    pedido.marcar_pagado(Dinero(100, "MXN"))

    spec = PedidoPagadoSpec()
    assert spec.is_satisfied_by(pedido) is True


def test_pedido_entregado_spec() -> None:
    """US-013: Pedido en estado ENTREGADO para devolución."""
    from uuid import uuid4

    from src.domain.entities import Surtido
    from src.domain.value_objects import Guia

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00006"), 1, Dinero(100, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    surtido = Surtido(id=uuid4(), pedido_id=pedido.id, almacen_id=uuid4(), lineas=[linea])
    pedido.asignar_surtidos([surtido])
    pedido.marcar_pagado(Dinero(100, "MXN"))
    pedido.iniciar_preparacion()
    pedido.confirmar_empaque(almacen_id=surtido.almacen_id)
    pedido.marcar_enviado(Guia("TRACK-001"))
    # Simular entrega exitosa
    pedido._transicionar(EstadoPedido.ENTREGADO)

    spec = PedidoEntregadoSpec()
    assert spec.is_satisfied_by(pedido) is True


def test_stock_suficiente_spec() -> None:
    """US-001, US-002: Stock suficiente para cantidad requerida."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00007")
    ex = almacen.agregar_existencia(producto_id, sku, 20)

    spec_10 = StockSuficienteSpec(10)
    spec_25 = StockSuficienteSpec(25)

    assert spec_10.is_satisfied_by(ex) is True
    assert spec_25.is_satisfied_by(ex) is False


def test_spec_combinada_and() -> None:
    """Combinación AND de especificaciones."""
    from src.domain.aggregates import Producto

    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00008")
    almacen.agregar_existencia(producto_id, sku, 10)

    producto = Producto.crear(sku, "Producto", "Desc", Dinero(100, "MXN"), "Alimentos")

    spec_activo = ProductoActivoSpec()
    spec_disponible = ProductoDisponibleSpec(almacen, 5)
    combinada = spec_activo.and_(spec_disponible)

    assert combinada.is_satisfied_by(producto) is True


def test_spec_combinada_or() -> None:
    """Combinación OR de especificaciones."""
    from src.domain.aggregates import Producto

    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00009")
    almacen.agregar_existencia(producto_id, sku, 2)

    producto = Producto.crear(sku, "Producto", "Desc", Dinero(100, "MXN"), "Alimentos")

    spec_activo = ProductoActivoSpec()
    spec_disponible_10 = ProductoDisponibleSpec(almacen, 10)  # No hay stock
    combinada = spec_activo.or_(spec_disponible_10)

    assert combinada.is_satisfied_by(producto) is True  # Activo es True


def test_spec_combinada_not() -> None:
    """Negación de especificación."""
    from src.domain.aggregates import Producto

    producto_inactivo = Producto.crear(
        Sku.of("SKU-00010"), "Producto", "Desc", Dinero(100, "MXN"), "Alimentos"
    )
    producto_inactivo.desactivar()

    spec_activo = ProductoActivoSpec()
    spec_no_activo = spec_activo.not_()

    assert spec_no_activo.is_satisfied_by(producto_inactivo) is True


def test_pago_aprobable_spec_exacto() -> None:
    """US-004: Pago aprobable con monto exacto."""
    from uuid import uuid4

    from src.domain.entities import Surtido

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00011"), 2, Dinero(50, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    surtido = Surtido(id=uuid4(), pedido_id=pedido.id, almacen_id=uuid4(), lineas=[linea])
    pedido.asignar_surtidos([surtido])

    spec = PagoAprobableSpec(Dinero(100, "MXN"))
    assert spec.is_satisfied_by(pedido) is True


def test_pago_aprobable_spec_diferente_moneda() -> None:
    """US-004: Pago no aprobable con moneda distinta."""
    from uuid import uuid4

    from src.domain.entities import Surtido

    direccion = DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000")
    linea = LineaPedido(Sku.of("SKU-00012"), 1, Dinero(100, "MXN"))
    pedido = Pedido.crear(uuid4(), [linea], direccion)
    surtido = Surtido(id=uuid4(), pedido_id=pedido.id, almacen_id=uuid4(), lineas=[linea])
    pedido.asignar_surtidos([surtido])

    spec = PagoAprobableSpec(Dinero(100, "USD"))  # Distinta moneda
    assert spec.is_satisfied_by(pedido) is False