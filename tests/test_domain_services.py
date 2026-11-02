"""Tests unitarios - Domain Services.

US-006: Asignación de almacenes.
"""
from __future__ import annotations

from uuid import uuid4

from src.domain.aggregates import Almacen
from src.domain.entities import LineaPedido
from src.domain.exceptions import StockInsuficienteError
from src.domain.services import AsignacionAlmacenService
from src.domain.value_objects import DireccionEntrega, Dinero, Sku


def test_asignacion_almacen_service_un_solo_almacen() -> None:
    """US-006: Asignación a un solo almacén."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-10001")
    almacen.agregar_existencia(producto_id, sku, 10)

    lineas = [LineaPedido(sku, 2, Dinero(50, "MXN"))]
    service = AsignacionAlmacenService()
    surtidos = service.asignar(lineas, [almacen])

    assert len(surtidos) == 1
    assert surtidos[0].almacen_id == almacen.id
    assert len(surtidos[0].lineas) == 1


def test_asignacion_almacen_service_dos_almacenes() -> None:
    """US-006: Pedido dividido entre dos almacenes."""
    almacen_norte = Almacen.crear("Norte", "Monterrey")
    almacen_sur = Almacen.crear("Sur", "Guadalajara")

    producto_id = uuid4()
    sku_1 = Sku.of("SKU-20001")
    sku_2 = Sku.of("SKU-20002")

    almacen_norte.agregar_existencia(producto_id, sku_1, 5)
    almacen_sur.agregar_existencia(producto_id, sku_2, 3)

    lineas = [
        LineaPedido(sku_1, 2, Dinero(100, "MXN")),
        LineaPedido(sku_2, 1, Dinero(150, "MXN")),
    ]
    service = AsignacionAlmacenService()
    surtidos = service.asignar(lineas, [almacen_norte, almacen_sur])

    assert len(surtidos) == 2
    almacenes_ids = {s.almacen_id for s in surtidos}
    assert len(almacenes_ids) == 2


def test_asignacion_almacen_stock_insuficiente() -> None:
    """US-005: Stock insuficiente lanza excepción."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-30001")
    almacen.agregar_existencia(producto_id, sku, 2)

    lineas = [LineaPedido(sku, 5, Dinero(50, "MXN"))]
    service = AsignacionAlmacenService()

    try:
        service.asignar(lineas, [almacen])
        assert False, "Debería haber lanzado StockInsuficienteError"
    except StockInsuficienteError:
        pass


def test_asignacion_almacen_sin_almacenes() -> None:
    """Sin almacenes debe lanzar error."""
    lineas = [LineaPedido(Sku.of("SKU-40001"), 1, Dinero(100, "MXN"))]
    service = AsignacionAlmacenService()

    try:
        service.asignar(lineas, [])
        assert False, "Debería haber lanzado ValueError"
    except ValueError:
        pass


def test_asignacion_almacen_multiple_lineas_mismo_almacen() -> None:
    """Múltiples líneas asignadas al mismo almacén."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku_1 = Sku.of("SKU-50001")
    sku_2 = Sku.of("SKU-50002")
    almacen.agregar_existencia(producto_id, sku_1, 10)
    almacen.agregar_existencia(producto_id, sku_2, 10)

    lineas = [
        LineaPedido(sku_1, 2, Dinero(50, "MXN")),
        LineaPedido(sku_2, 3, Dinero(75, "MXN")),
    ]
    service = AsignacionAlmacenService()
    surtidos = service.asignar(lineas, [almacen])

    assert len(surtidos) == 1
    assert len(surtidos[0].lineas) == 2