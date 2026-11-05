"""Tests unitarios del dominio - Almacén e inventario.

US-001, US-002, US-005, US-006
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.aggregates import Almacen
from src.domain.exceptions import StockInsuficienteError
from src.domain.value_objects import Sku


def test_almacen_reserva_stock() -> None:
    """US-001: Reserva de inventario durante checkout por 15 min."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00003")
    almacen.agregar_existencia(producto_id, sku, 10)

    almacen.reservar(sku, 5, uuid4())
    ex = almacen.obtener_existencia(sku)
    assert ex.disponible_para_venta == 5
    assert ex.cantidad_reservada == 5


def test_almacen_stock_insuficiente() -> None:
    """US-005: Producto agotado durante proceso de compra."""
    almacen = Almacen.crear("Sur", "Guadalajara")
    producto_id = uuid4()
    sku = Sku.of("SKU-00004")
    almacen.agregar_existencia(producto_id, sku, 2)

    with pytest.raises(StockInsuficienteError):
        almacen.reservar(sku, 5, uuid4())


def test_almacen_liberar_reserva() -> None:
    """US-002: Liberación automática de reserva tras 15 min sin pago."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00005")
    almacen.agregar_existencia(producto_id, sku, 10)

    pedido_id = uuid4()
    almacen.reservar(sku, 3, pedido_id)
    almacen.liberar_reserva(sku, 3)

    ex = almacen.obtener_existencia(sku)
    assert ex.disponible_para_venta == 10
    assert ex.cantidad_reservada == 0


def test_almacen_confirmar_venta() -> None:
    """US-004: Al confirmar pago, se descuenta stock real."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00006")
    almacen.agregar_existencia(producto_id, sku, 10)

    almacen.reservar(sku, 4, uuid4())
    almacen.confirmar_venta(sku, 4)

    ex = almacen.obtener_existencia(sku)
    assert ex.cantidad_disponible == 6
    assert ex.cantidad_reservada == 0


def test_almacen_reponer_stock_cancelado_pagado() -> None:
    """US-008: Al cancelar un pedido PAGADO, el stock se repone.

    Cuando un pedido ya pagado se cancela (por el cliente o con autorización),
    se debe reponer el stock que fue confirmado/descuentado.
    """
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00007")
    almacen.agregar_existencia(producto_id, sku, 10)

    # Simular: reserva -> confirmar venta (pago aprobado) -> cancelar
    almacen.reservar(sku, 3, uuid4())
    almacen.confirmar_venta(sku, 3)

    # Verificar stock confirmado
    ex = almacen.obtener_existencia(sku)
    assert ex.cantidad_disponible == 7
    assert ex.cantidad_reservada == 0

    # Cancelar: reponer stock
    almacen.reponer(sku, 3)

    # Verificar reposición
    ex_final = almacen.obtener_existencia(sku)
    assert ex_final.cantidad_disponible == 10
    assert ex_final.cantidad_reservada == 0