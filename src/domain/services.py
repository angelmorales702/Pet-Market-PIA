"""Domain Services - PetMarket.

Servicios de dominio que encapsulan lógica de negocio que no pertenece a un solo agregado.
Alineados con docs/fuentes/Diagrama_de_clases.md y Diagramas_DDD.md
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from .aggregates import Almacen, Pedido
from .entities import Surtido
from .events import StockInsuficienteEvent
from .value_objects import Sku

# ============================================================================
# RELOJ INYECTABLE Y CALENDARIO DE DÍAS HÁBILES
# ============================================================================

class Reloj(ABC):
    """Interfaz para un reloj inyectable (permite tests determinísticos)."""

    @abstractmethod
    def ahora(self) -> datetime:
        pass


class RelojSistema(Reloj):
    """Implementación que usa el reloj del sistema."""

    def ahora(self) -> datetime:
        return datetime.now(timezone.utc)


class RelojFijo(Reloj):
    """Reloj para tests: devuelve una fecha fija."""

    def __init__(self, fecha: datetime):
        self._fecha = fecha

    def ahora(self) -> datetime:
        return self._fecha


class CalendarioDiasHabiles(ABC):
    """Interfaz para cálculo de días hábiles (excluye fines de semana y festivos)."""

    @abstractmethod
    def agregar_dias_habiles(self, fecha_inicio: datetime, dias: int) -> datetime:
        pass


class CalendarioDiasHabilesBasico(CalendarioDiasHabiles):
    """Implementación básica: lunes a viernes, sin festivos configurados."""

    def __init__(self):
        self._festivos: set[datetime] = set()

    def agregar_dias_habiles(self, fecha_inicio: datetime, dias: int) -> datetime:
        fecha = fecha_inicio
        agregados = 0
        while agregados < dias:
            fecha += timedelta(days=1)
            if fecha.weekday() < 5 and fecha not in self._festivos:  # Lun-Vie
                agregados += 1
        return fecha

    def agregar_festivo(self, fecha: datetime) -> None:
        self._festivos.add(fecha)


# Instancias por defecto (se pueden sobrescribir en tests)
RELOJ_DEFECTO = RelojSistema()
CALENDARIO_DEFECTO = CalendarioDiasHabilesBasico()


# ============================================================================
# SERVICIO: ASIGNACIÓN DE ALMACÉN
# ============================================================================

class AsignacionAlmacenService:
    """US-006: Divide el pedido en surtidos por almacén según disponibilidad.

    Algoritmo:
    1. Para cada línea, busca almacén con stock suficiente.
    2. Si una línea tiene stock en múltiples almacenes, prioriza el que tiene más stock.
    3. Si una línea no tiene stock en ningún almacén, emite StockInsuficienteEvent y quita solo esa línea.
    """

    def __init__(
        self,
        reloj: Optional[Reloj] = None,
        calendario: Optional[CalendarioDiasHabiles] = None,
    ):
        self._reloj = reloj or RELOJ_DEFECTO
        self._calendario = calendario or CALENDARIO_DEFECTO

    def asignar(
        self,
        pedido: Pedido,
        almacenes: List[Almacen],
        reservar: bool = True,
    ) -> List[Surtido]:
        """Asigna líneas del pedido a almacenes y crea surtidos.

        Retorna lista de Surtido creados. Si alguna línea no tiene stock en ningún
        almacén, emite StockInsuficienteEvent y no la incluye en ningún surtido.
        """
        if not almacenes:
            raise ValueError("Se requiere al menos un almacén para asignar el pedido")

        surtidos_por_almacen: dict[UUID, Surtido] = {}

        for linea in pedido.lineas:
            almacen_seleccionado = None
            max_stock = 0

            for almacen in almacenes:
                ex = almacen.obtener_existencia(linea.sku)
                if ex and ex.disponible_para_venta >= linea.cantidad:
                    if ex.disponible_para_venta > max_stock:
                        max_stock = ex.disponible_para_venta
                        almacen_seleccionado = almacen

            if almacen_seleccionado is None:
                # No hay stock en ningún almacén -> emitir evento y omitir la línea
                for almacen in almacenes:
                    almacen.add_domain_event(StockInsuficienteEvent(
                        pedido_id=pedido.id,
                        almacen_id=almacen.id,
                        sku=str(linea.sku),
                        solicitado=linea.cantidad,
                        disponible=0,
                    ))
                continue

            # Reservar stock si se solicita
            if reservar:
                almacen_seleccionado.reservar(linea.sku, linea.cantidad, pedido.id)

            # Agregar línea al surtido correspondiente
            if almacen_seleccionado.id not in surtidos_por_almacen:
                surtidos_por_almacen[almacen_seleccionado.id] = Surtido(
                    id=uuid4(),
                    pedido_id=pedido.id,
                    almacen_id=almacen_seleccionado.id,
                    lineas=[],
                )
            surtidos_por_almacen[almacen_seleccionado.id].agregar_linea(linea)

        # Validar que todos los surtidos tengan al menos una línea
        for surtido in surtidos_por_almacen.values():
            surtido.validar_no_vacio()

        return list(surtidos_por_almacen.values())


# ============================================================================
# SERVICIO: LIBERACIÓN DE RESERVAS EXPIRADAS (15 MIN)
# ============================================================================

class ReservaExpiradaService:
    """US-002: Libera reservas que han expirado (15 minutos sin pago).

    En producción, esto se ejecutaría como un job programado.
    """

    def __init__(
        self,
        reloj: Optional[Reloj] = None,
        minutos_reserva: int = 15,
    ):
        self._reloj = reloj or RELOJ_DEFECTO
        self._minutos_reserva = minutos_reserva

    def liberar_reservas_expiradas(self, almacenes: List[Almacen]) -> None:
        """Recorre almacenes y libera reservas > 15 min."""
        ahora = self._reloj.ahora()
        # En la implementación real, ExistenciaProducto guardaría timestamp de reserva
        # Aquí es un placeholder - la lógica real está en ExistenciaProducto
        pass


# ============================================================================
# ESPECIFICACIONES ADICIONALES
# ============================================================================

from .specifications import Specification


class PedidoPendienteDePagoSpec(Specification[Pedido]):
    """US-004: Pedido está en PENDIENTE_PAGO (esperando pago)."""

    def is_satisfied_by(self, candidato: Pedido) -> bool:
        from .state_machine import EstadoPedido
        return candidato.estado == EstadoPedido.PENDIENTE_PAGO


class PedidoConStockReservadoSpec(Specification[Pedido]):
    """US-001: Pedido tiene stock reservado en todos sus surtidos."""

    def is_satisfied_by(self, candidato: Pedido) -> bool:
        if not candidato.surtidos:
            return False
        # En la implementación real, verificaríamos que cada surtido tiene reservas activas
        return True


class DiscrepanciaInventarioSpec(Specification[Almacen]):
    """US-016: Detecta si un almacén tiene discrepancias de inventario."""

    def __init__(self, sku: Sku, cantidad_fisica: int):
        self._sku = sku
        self._cantidad_fisica = cantidad_fisica

    def is_satisfied_by(self, candidato: Almacen) -> bool:
        ex = candidato.obtener_existencia(self._sku)
        cantidad_web = ex.cantidad_disponible if ex else 0
        return cantidad_web != self._cantidad_fisica