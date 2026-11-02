"""Domain Services del dominio PetMarket.

Los Domain Services encapsulan lógica de negocio que no pertenece
naturalmente a una sola Entidad o Value Object, y que coordina
múltiples agregados.

Alineados con docs/fuentes/Diagrama_de_clases.md (AsignacionAlmacenService)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from .aggregates import Almacen, Pedido
from .entities import LineaPedido, Surtido
from .events import StockInsuficienteEvent
from .exceptions import StockInsuficienteError
from .value_objects import Sku


@dataclass
class AsignacionAlmacenService:
    """Domain Service: Asignación de almacenes para un pedido.

    Determina cómo se dividen las líneas de un pedido entre los almacenes
    disponibles según la existencia de stock.

    US-006: Pedido con productos en dos almacenes.
    ADR-002: El pedido se divide en Surtidos por almacén.

    # SUPUESTO: Estrategia por defecto "menor número de almacenes".
    # Validar con el negocio si se requieren otras estrategias (más cercano, etc.).
    """

    def asignar(
        self,
        lineas: list[LineaPedido],
        almacenes: list[Almacen],
    ) -> list[Surtido]:
        """Asigna cada línea al almacén que tenga stock suficiente.

        Retorna una lista de Surtidos, cada uno con sus líneas asignadas a un almacén.
        Lanza StockInsuficienteError si algún SKU no tiene stock en ningún almacén.
        """
        if not almacenes:
            raise ValueError("Debe haber al menos un almacén")

        # Mapa: almacen_id -> líneas asignadas
        lineas_por_almacen: dict[UUID, list[LineaPedido]] = {}

        for linea in lineas:
            almacen_asignado = self._encontrar_almacen_con_stock(linea, almacenes)
            if not almacen_asignado:
                # Emitir evento de stock insuficiente (lo haría la capa de aplicación)
                raise StockInsuficienteError(
                    str(linea.sku), linea.cantidad, 0
                )

            if almacen_asignado.id not in lineas_por_almacen:
                lineas_por_almacen[almacen_asignado.id] = []
            lineas_por_almacen[almacen_asignado.id].append(linea)

        # Crear Surtidos
        surtidos = []
        for almacen_id, lineas_asignadas in lineas_por_almacen.items():
            surtido = Surtido(
                id=UUID(int=0),  # Se asignará ID real al persistir
                pedido_id=UUID(int=0),  # Se asignará al crear el pedido
                almacen_id=almacen_id,
                lineas=lineas_asignadas,
            )
            surtidos.append(surtido)

        return surtidos

    def _encontrar_almacen_con_stock(
        self,
        linea: LineaPedido,
        almacenes: list[Almacen],
    ) -> Optional[Almacen]:
        """Encuentra el primer almacén con stock suficiente para la línea.

        # SUPUESTO: Estrategia simple "primer almacén con stock".
        # Validar con el negocio: ¿priorizar almacén con más stock? ¿más cercano?
        """
        for almacen in almacenes:
            ex = almacen.obtener_existencia(linea.sku)
            if ex and ex.disponible_para_venta >= linea.cantidad:
                return almacen
        return None


@dataclass
class ResultadoAsignacion:
    """Resultado de la asignación de almacenes."""
    surtidos: list[Surtido]
    lineas_no_asignadas: list[LineaPedido]  # Líneas que no pudieron asignarse