"""Tests para nuevas funcionalidades (US-016)."""
from uuid import uuid4
from src.domain.aggregates import Almacen
from src.domain.value_objects import Sku
from src.domain.events import DiscrepanciaInventarioDetectadaEvent

def test_almacen_detectar_discrepancia() -> None:
    """US-016: Discrepancia inventario web vs físico."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-00007")
    almacen.agregar_existencia(producto_id, sku, 10)

    # Cantidad física menor
    almacen.detectar_discrepancia(sku, 8)

    eventos = [e for e in almacen.domain_events if isinstance(e, DiscrepanciaInventarioDetectadaEvent)]
    assert len(eventos) == 1
    assert eventos[0].diferencia == -2
