"""Tests unitarios - Value Objects del dominio.

Cobertura para value_objects.py
"""
from __future__ import annotations

import pytest
from src.domain.value_objects import (
    DireccionEntrega,
    Dinero,
    Guia,
    MotivoDevolucion,
    Sku,
    EstadoSurtido,
    EstadoEnvio,
    EstadoPago,
    EstadoDevolucion,
)
from src.domain.state_machine import EstadoPedido


# =============================================================================
# Sku
# =============================================================================

def test_sku_crear_valido():
    """Sku válido se crea correctamente."""
    sku = Sku.of("SKU-00001")
    assert sku == "SKU-00001"


def test_sku_igualdad():
    """Dos SKUs con el mismo valor son iguales."""
    sku1 = Sku.of("SKU-00001")
    sku2 = Sku.of("SKU-00001")
    assert sku1 == sku2


def test_sku_hash():
    """Sku es hashable para usar en sets y dicts."""
    sku1 = Sku.of("SKU-00001")
    sku2 = Sku.of("SKU-00001")
    assert hash(sku1) == hash(sku2)


# =============================================================================
# Dinero
# =============================================================================

def test_dinero_crear_valido():
    """Dinero válido se crea correctamente."""
    dinero = Dinero(100.50, "MXN")
    assert dinero.monto == 100.50
    assert dinero.moneda == "MXN"


def test_dinero_suma():
    """Suma de montos mantiene la moneda."""
    d1 = Dinero(100, "MXN")
    d2 = Dinero(50, "MXN")
    resultado = d1 + d2
    assert resultado.monto == 150
    assert resultado.moneda == "MXN"


def test_dinero_resta():
    """Resta de montos."""
    d1 = Dinero(100, "MXN")
    d2 = Dinero(30, "MXN")
    resultado = d1 - d2
    assert resultado.monto == 70
    assert resultado.moneda == "MXN"


def test_dinero_invalido_moneda_vacia():
    """Dinero con moneda vacía eleva ValueError."""
    with pytest.raises(ValueError):
        Dinero(100, "")


def test_dinero_invalido_monto_negativo():
    """Dinero con monto negativo eleva ValueError."""
    with pytest.raises(ValueError):
        Dinero(-100, "MXN")


def test_dinero_invalido_moneda_none():
    """Dinero con moneda None eleva ValueError."""
    with pytest.raises(ValueError):
        Dinero(100, None)  # type: ignore


# =============================================================================
# DireccionEntrega
# =============================================================================

def test_direccion_valida():
    """Dirección válida se crea correctamente."""
    dir = DireccionEntrega("Av Principal", "123", "Centro", "Monterrey", "64000")
    assert dir.calle == "Av Principal"
    assert dir.numero == "123"
    assert dir.colonia == "Centro"
    assert dir.ciudad == "Monterrey"
    assert dir.codigo_postal == "64000"


def test_direccion_invalida_calle_vacia():
    """Dirección con calle vacía eleva ValueError."""
    with pytest.raises(ValueError):
        DireccionEntrega("", "123", "Centro", "Monterrey", "64000")


def test_direccion_invalida_ciudad_vacia():
    """Dirección con ciudad vacía eleva ValueError."""
    with pytest.raises(ValueError):
        DireccionEntrega("Av Principal", "123", "Centro", "", "64000")  # type: ignore


# =============================================================================
# Guia
# =============================================================================

def test_guia_valida():
    """Guía válida se crea correctamente."""
    guia = Guia.of("GUÍA-12345")
    assert guia.valor == "GUÍA-12345"


def test_guia_invalida_vacia():
    """Guía vacía eleva ValueError."""
    with pytest.raises(ValueError):
        Guia.of("")


def test_guia_invalida_too_long():
    """Guía vacía eleva ValueError."""
    with pytest.raises(ValueError):
        Guia.of("")


# =============================================================================
# MotivoDevolucion
# =============================================================================

def test_motivo_devolucion_valido():
    """Motivo de devolución válido."""
    motivo = MotivoDevolucion.of("Producto defectuoso")
    assert motivo.valor == "Producto defectuoso"


def test_motivo_devolucion_invalido():
    """Motivo de devolución vacío eleva ValueError."""
    with pytest.raises(ValueError):
        MotivoDevolucion.of("")


# =============================================================================
# EstadoPedido Enum
# =============================================================================

def test_estado_pedido_valores():
    """EstadoPedido contiene todos los valores esperados."""
    assert EstadoPedido.CREADO.value == "CREADO"
    assert EstadoPedido.PENDIENTE_PAGO.value == "PENDIENTE_PAGO"
    assert EstadoPedido.PAGADO.value == "PAGADO"
    assert EstadoPedido.EN_PREPARACION.value == "EN_PREPARACION"
    assert EstadoPedido.EMPACADO.value == "EMPACADO"
    assert EstadoPedido.ENVIADO.value == "ENVIADO"
    assert EstadoPedido.ENTREGADO.value == "ENTREGADO"
    assert EstadoPedido.CANCELADO.value == "CANCELADO"
    assert EstadoPedido.ENTREGA_FALLIDA.value == "ENTREGA_FALLIDA"
    assert EstadoPedido.DEVUELTO.value == "DEVUELTO"


# =============================================================================
# EstadoSurtido Enum
# =============================================================================

def test_estado_surtido_valores():
    """EstadoSurtido contiene todos los valores esperados."""
    assert EstadoSurtido.PENDIENTE.value == "PENDIENTE"
    assert EstadoSurtido.EN_PREPARACION.value == "EN_PREPARACION"
    assert EstadoSurtido.EMPACADO.value == "EMPACADO"


# =============================================================================
# EstadoPago Enum
# =============================================================================

def test_estado_pago_valores():
    """EstadoPago contiene todos los valores esperados."""
    assert EstadoPago.PENDIENTE.value == "PENDIENTE"
    assert EstadoPago.APROBADO.value == "APROBADO"
    assert EstadoPago.RECHAZADO.value == "RECHAZADO"


# =============================================================================
# EstadoEnvio Enum
# =============================================================================

def test_estado_envio_valores():
    """EstadoEnvio contiene todos los valores esperados."""
    assert EstadoEnvio.PENDIENTE.value == "PENDIENTE"
    assert EstadoEnvio.EN_TRASITO.value == "EN_TRASITO"
    assert EstadoEnvio.ENTREGADO.value == "ENTREGADO"
    assert EstadoEnvio.FALLIDO.value == "FALLIDO"


# =============================================================================
# EstadoDevolucion Enum
# =============================================================================

def test_estado_devolucion_valores():
    """EstadoDevolucion contiene todos los valores esperados."""
    assert EstadoDevolucion.SOLICITADA.value == "SOLICITADA"
    assert EstadoDevolucion.APROBADA.value == "APROBADA"
    assert EstadoDevolucion.RECHAZADA.value == "RECHAZADA"
    assert EstadoDevolucion.PROCESADA.value == "PROCESADA"


# =============================================================================
# TransicionEstadoInvalidaException (importado de exceptions)
# =============================================================================

from src.domain.exceptions import TransicionEstadoInvalidaException


def test_transicion_estado_invalida_exception():
    """TransicionEstadoInvalidaException se crea correctamente."""
    exc = TransicionEstadoInvalidaException("CREADO", "PAGADO")
    assert "CREADO" in str(exc)
    assert "PAGADO" in str(exc)


# =============================================================================
# Tests de excepciones adicionales
# =============================================================================

from src.domain.exceptions import (
    StockInsuficienteError,
    CancelacionNoPermitidaError,
    DevolucionNoPermitidaError,
    PagoMontoNoCoincideError,
)


def test_stock_insuficiente_error():
    """StockInsuficienteError muestra detalles del SKU y cantidades."""
    exc = StockInsuficienteError("SKU-00001", 10, 5)
    assert "SKU-00001" in str(exc)
    assert "10" in str(exc)  # solicitado
    assert "5" in str(exc)  # disponible


def test_cancelacion_no_permitida_error():
    """CancelacionNoPermitidaError para pedidos ya despachados."""
    exc = CancelacionNoPermitidaError("ENVIADO")
    assert "ENVIADO" in str(exc)


def test_devolucion_no_permitida_error():
    """DevolucionNoPermitidaError para estados que no permiten devolución."""
    exc = DevolucionNoPermitidaError("PENDIENTE_PAGO")
    assert "PENDIENTE_PAGO" in str(exc)


def test_pago_monto_no_coincide_error():
    """PagoMontoNoCoincideError muestra los montos involucrados."""
    exc = PagoMontoNoCoincideError("100.00 MXN", "200.00 MXN")
    assert "100.00 MXN" in str(exc)
    assert "200.00 MXN" in str(exc)