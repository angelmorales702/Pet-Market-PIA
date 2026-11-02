"""Tests unitarios - Devolución.

US-013, US-014, US-015
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.domain.aggregates import Devolucion
from src.domain.entities import LineaDevolucion
from src.domain.value_objects import MotivoDevolucion, Sku


def test_devolucion_solicitar_dentro_ventana() -> None:
    """US-013: Devolución solicitada dentro de 5 días hábiles."""
    lineas = [LineaDevolucion(Sku.of("SKU-00011"), 1)]
    motivo = MotivoDevolucion("Producto defectuoso")
    devolucion = Devolucion.solicitar(uuid4(), lineas, motivo)

    # Simular fecha de entrega hace 3 días hábiles
    fecha_entrega = datetime.now() - timedelta(days=3)
    assert devolucion.esta_dentro_ventana(fecha_entrega, dias_habiles=5) is True


def test_devolucion_fuera_ventana() -> None:
    """US-013: Devolución rechazada fuera de plazo."""
    lineas = [LineaDevolucion(Sku.of("SKU-00012"), 1)]
    motivo = MotivoDevolucion("No me gusta")
    devolucion = Devolucion.solicitar(uuid4(), lineas, motivo)

    # Simular fecha de entrega hace 10 días hábiles
    fecha_entrega = datetime.now() - timedelta(days=12)
    assert devolucion.esta_dentro_ventana(fecha_entrega, dias_habiles=5) is False


def test_devolucion_flujo_autorizacion_recepcion_reembolso() -> None:
    """US-014 y US-015: Flujo completo de devolución."""
    lineas = [LineaDevolucion(Sku.of("SKU-00013"), 1)]
    motivo = MotivoDevolucion("Producto roto")
    devolucion = Devolucion.solicitar(uuid4(), lineas, motivo)

    assert devolucion.estado.value == "SOLICITADA"

    devolucion.autorizar()
    assert devolucion.estado.value == "APROBADA"

    devolucion.confirmar_recepcion_almacen()
    assert devolucion.estado.value == "PROCESADA"

    devolucion.marcar_reembolsado()
    assert devolucion.fecha_reembolso is not None


def test_devolucion_no_autorizar_sin_solicitud() -> None:
    """Devolución no puede autorizarse si no está SOLICITADA."""
    from src.domain.value_objects import EstadoDevolucion
    from src.domain.exceptions import TransicionEstadoInvalidaException

    lineas = [LineaDevolucion(Sku.of("SKU-00014"), 1)]
    motivo = MotivoDevolucion("Motivo")
    devolucion = Devolucion.solicitar(uuid4(), lineas, motivo)

    # Cambiar estado manualmente para simular error
    devolucion.estado = EstadoDevolucion.PROCESADA

    with pytest.raises(TransicionEstadoInvalidaException):
        devolucion.autorizar()