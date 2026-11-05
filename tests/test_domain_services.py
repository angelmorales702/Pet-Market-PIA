"""Tests unitarios - Domain Services.

US-006: Asignación de almacenes.
US-002: Reserva 15 min (reloj inyectable).
US-013: Días hábiles (calendario).
US-016: Discrepancia inventario.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.domain.aggregates import Almacen, Pedido
from src.domain.entities import LineaPedido
from src.domain.services import (
    AsignacionAlmacenService,
    CalendarioDiasHabilesBasico,
    DiscrepanciaInventarioSpec,
    RelojFijo,
)
from src.domain.state_machine import EstadoPedido
from src.domain.value_objects import Dinero, DireccionEntrega, Sku


def _crear_pedido(lineas: list[LineaPedido]) -> Pedido:
    return Pedido(
        id=uuid4(),
        cliente_id=uuid4(),
        lineas=lineas,
        direccion_entrega=DireccionEntrega("Calle", "1", "Col", "Ciudad", "64000"),
        estado=EstadoPedido.CREADO,
    )


def test_asignacion_almacen_service_un_solo_almacen() -> None:
    """US-006: Asignación a un solo almacén."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-10001")
    almacen.agregar_existencia(producto_id, sku, 10)

    pedido = _crear_pedido([LineaPedido(sku, 2, Dinero(50, "MXN"))])
    service = AsignacionAlmacenService()
    surtidos = service.asignar(pedido, [almacen])

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

    pedido = _crear_pedido([
        LineaPedido(sku_1, 2, Dinero(100, "MXN")),
        LineaPedido(sku_2, 1, Dinero(150, "MXN")),
    ])
    service = AsignacionAlmacenService()
    surtidos = service.asignar(pedido, [almacen_norte, almacen_sur])

    assert len(surtidos) == 2
    almacenes_ids = {s.almacen_id for s in surtidos}
    assert len(almacenes_ids) == 2


def test_asignacion_almacen_stock_insuficiente_emite_evento_y_omite_linea() -> None:
    """US-005: Stock insuficiente -> solo se emite evento, se omite la línea (no excepción)."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-30001")
    almacen.agregar_existencia(producto_id, sku, 2)

    pedido = _crear_pedido([LineaPedido(sku, 5, Dinero(50, "MXN"))])
    service = AsignacionAlmacenService()
    surtidos = service.asignar(pedido, [almacen])

    # No hay surtidos creados porque la línea no tiene stock
    assert len(surtidos) == 0
    # Se emitió el evento
    eventos = almacen.domain_events
    assert any(e.__class__.__name__ == "StockInsuficienteEvent" for e in eventos)


def test_asignacion_almacen_sin_almacenes() -> None:
    """Sin almacenes debe lanzar error."""
    pedido = _crear_pedido([LineaPedido(Sku.of("SKU-40001"), 1, Dinero(100, "MXN"))])
    service = AsignacionAlmacenService()

    try:
        service.asignar(pedido, [])
        raise AssertionError("Debería haber lanzado ValueError")
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

    pedido = _crear_pedido([
        LineaPedido(sku_1, 2, Dinero(50, "MXN")),
        LineaPedido(sku_2, 3, Dinero(75, "MXN")),
    ])
    service = AsignacionAlmacenService()
    surtidos = service.asignar(pedido, [almacen])

    assert len(surtidos) == 1
    assert len(surtidos[0].lineas) == 2


# --- Tests Reloj inyectable (US-002) ---

def test_reloj_fijo_para_tests_deterministicos() -> None:
    """Reloj inyectable permite tests determinísticos de expiración de 15 min."""
    fecha_base = datetime(2024, 1, 15, 10, 0, 0)
    reloj = RelojFijo(fecha_base)
    assert reloj.ahora() == fecha_base


def test_reloj_fijo_avanzado() -> None:
    """Avanzar el reloj simula paso del tiempo."""
    fecha_base = datetime(2024, 1, 15, 10, 0, 0)
    reloj = RelojFijo(fecha_base)
    # Simular 20 min después
    reloj = RelojFijo(fecha_base + timedelta(minutes=20))
    assert reloj.ahora() > fecha_base + timedelta(minutes=15)


# --- Tests Calendario días hábiles (US-013) ---

def test_calendario_dias_habiles_basico_lunes_a_viernes() -> None:
    """Calendario cuenta solo días laborables (lunes-viernes)."""
    cal = CalendarioDiasHabilesBasico()
    # Lunes 15 ene 2024
    inicio = datetime(2024, 1, 15, 10, 0, 0)
    # 5 días hábiles -> lunes 22 ene
    fin = cal.agregar_dias_habiles(inicio, 5)
    assert fin == datetime(2024, 1, 22, 10, 0, 0)


def test_calendario_salta_fin_de_semana() -> None:
    """Calendario salta sábado y domingo."""
    cal = CalendarioDiasHabilesBasico()
    # Viernes 19 ene 2024
    inicio = datetime(2024, 1, 19, 10, 0, 0)
    # 1 día hábil -> lunes 22 ene
    fin = cal.agregar_dias_habiles(inicio, 1)
    assert fin == datetime(2024, 1, 22, 10, 0, 0)


def test_calendario_festivos() -> None:
    """Calendario puede excluir festivos."""
    cal = CalendarioDiasHabilesBasico()
    festivo = datetime(2024, 1, 16, 10, 0, 0)  # Martes 16
    cal.agregar_festivo(festivo)
    inicio = datetime(2024, 1, 15, 10, 0, 0)  # Lunes 15
    # 1 día hábil -> miércoles 17 (martes es festivo)
    fin = cal.agregar_dias_habiles(inicio, 1)
    assert fin == datetime(2024, 1, 17, 10, 0, 0)


# --- Tests reloj en dominio (US-002, US-013) ---

def test_esta_dentro_ventana_con_reloj_fijo() -> None:
    """US-013: esta_dentro_ventana respeta el calendario inyectado y el reloj inyectado.

    US-013: 5 días hábiles posteriores a la entrega.
    Entrega: lunes 15 ene 2024 (15:00 UTC)
    Límite: lunes 22 ene 2024 (15:00 UTC) - 5 días hábiles exactos

    Casos probados:
    - Miércoles 17 ene 2024 (dentro de la ventana) -> True
    - Martes 23 ene 2024 (fuera de la ventana) -> False
    """
    from src.domain.aggregates import Devolucion
    from src.domain.entities import LineaDevolucion
    from src.domain.value_objects import MotivoDevolucion, Sku

    lineas = [LineaDevolucion(Sku.of("SKU-99999"), 1)]
    motivo = MotivoDevolucion("Test")
    dev = Devolucion.solicitar(uuid4(), lineas, motivo)

    # Con calendario inyectado (lunes -> viernes siguiente = 5 días hábiles)
    cal = CalendarioDiasHabilesBasico()
    # Entrega: lunes 15 ene 2024 -> límite: lunes 22 ene 2024
    fecha_entrega = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    # Caso 1: Miércoles 17 (dentro de la ventana)
    reloj_dentro = RelojFijo(datetime(2024, 1, 17, 10, 0, 0, tzinfo=timezone.utc))
    assert dev.esta_dentro_ventana(fecha_entrega, calendario=cal, reloj=reloj_dentro) is True

    # Caso 2: Martes 23 (fuera de la ventana)
    reloj_fuera = RelojFijo(datetime(2024, 1, 23, 10, 0, 0, tzinfo=timezone.utc))
    assert dev.esta_dentro_ventana(fecha_entrega, calendario=cal, reloj=reloj_fuera) is False


def test_reserva_expirada_service_usa_reloj_inyectado() -> None:
    """US-002: ReservaExpiradaService usa el reloj inyectado (no datetime.now directo)."""
    from datetime import timezone

    from src.domain.services import RelojFijo, ReservaExpiradaService

    fecha_base = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    reloj = RelojFijo(fecha_base)
    service = ReservaExpiradaService(reloj=reloj)
    # La instancia debe referenciar el reloj inyectado, no el sistema
    assert service._reloj is reloj
    assert service._reloj.ahora() == fecha_base


# --- Tests Discrepancia (US-016) ---

def test_discrepancia_inventario_spec_detecta_diferencia() -> None:
    """US-016: Specification detecta discrepancia web vs físico."""
    almacen = Almacen.crear("Norte", "Monterrey")
    producto_id = uuid4()
    sku = Sku.of("SKU-70001")
    almacen.agregar_existencia(producto_id, sku, 10)

    spec = DiscrepanciaInventarioSpec(sku, 8)  # físico = 8, web = 10
    assert spec.is_satisfied_by(almacen) is True

    spec_ok = DiscrepanciaInventarioSpec(sku, 10)  # igual
    assert spec_ok.is_satisfied_by(almacen) is False