"""Máquina de Estados Explícita para el Aggregate `Pedido`.

Implementada sin librerías externas. Define la tabla de transiciones, las
guardas y lanza `TransicionEstadoInvalidaException` cuando se solicita una
transición no permitida.

Estados del `Pedido` (alineados con Diagrama_de_clases.md):
  CREADO, PENDIENTE_PAGO, PAGADO, EN_PREPARACION, EMPACADO, ENVIADO,
  ENTREGADO, CANCELADO, ENTREGA_FALLIDA, DEVUELTO
"""
from __future__ import annotations

from enum import Enum
from typing import Callable, Dict, Set

from .exceptions import (
    CancelacionNoPermitidaError,
    DevolucionNoPermitidaError,
    PagoMontoNoCoincideError,
    TransicionEstadoInvalidaException,
)


class EstadoPedido(str, Enum):
    CREADO = "CREADO"
    PENDIENTE_PAGO = "PENDIENTE_PAGO"
    PAGADO = "PAGADO"
    EN_PREPARACION = "EN_PREPARACION"
    EMPACADO = "EMPACADO"
    ENVIADO = "ENVIADO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"
    ENTREGA_FALLIDA = "ENTREGA_FALLIDA"
    DEVUELTO = "DEVUELTO"


# Tabla de transiciones permitidas: estado_origen -> conjunto de estados destino
TRANSICIONES: Dict[EstadoPedido, Set[EstadoPedido]] = {
    EstadoPedido.CREADO: {
        EstadoPedido.PENDIENTE_PAGO,
        EstadoPedido.CANCELADO,
    },
    EstadoPedido.PENDIENTE_PAGO: {
        EstadoPedido.PAGADO,
        EstadoPedido.CANCELADO,
    },
    EstadoPedido.PAGADO: {
        EstadoPedido.CANCELADO,
        EstadoPedido.EN_PREPARACION,
    },
    EstadoPedido.EN_PREPARACION: {
        EstadoPedido.CANCELADO,
        EstadoPedido.EMPACADO,
    },
    EstadoPedido.EMPACADO: {
        EstadoPedido.CANCELADO,
        EstadoPedido.ENVIADO,
    },
    EstadoPedido.ENVIADO: {
        EstadoPedido.ENTREGADO,
        EstadoPedido.ENTREGA_FALLIDA,
    },
    EstadoPedido.ENTREGADO: {
        EstadoPedido.DEVUELTO,
    },
    EstadoPedido.ENTREGA_FALLIDA: {
        EstadoPedido.DEVUELTO,
    },
    EstadoPedido.CANCELADO: set(),
    EstadoPedido.DEVUELTO: set(),
}


# Contexto para las guardas: dict con información del contexto de la transición.
GuardaContext = Dict[str, object]


def _guard_pagado(contexto: GuardaContext) -> None:
    """Guarda: el monto del pago debe coincidir con el total del pedido."""
    pagado = contexto.get("pagado")
    total = contexto.get("total")
    if pagado is None or total is None:
        raise TransicionEstadoInvalidaException(
            str(contexto.get("estado_actual", "?")),
            str(contexto.get("estado_destino", "?")),
        )
    if pagado != total:
        raise PagoMontoNoCoincideError(str(pagado), str(total))


def _guard_preparacion(contexto: GuardaContext) -> None:
    """Guarda: se inicia la preparación cuando el pedido está pagado."""
    # No hay validaciones adicionales, solo la transición CREADO -> PENDIENTE_PAGO -> PAGADO -> EN_PREPARACION
    pass


def _guard_empacado(contexto: GuardaContext) -> None:
    """Guarda: todos los surtidos deben estar en estado EMPACADO."""
    surtidos = contexto.get("surtidos")
    if not surtidos:
        raise TransicionEstadoInvalidaException(
            str(contexto.get("estado_actual", "?")),
            str(contexto.get("estado_destino", "?")),
        )
    from .value_objects import EstadoSurtido

    no_empacados = [
        s for s in surtidos
        if getattr(s, "estado", None) != EstadoSurtido.EMPACADO
    ]
    if no_empacados:
        raise TransicionEstadoInvalidaException(
            str(contexto.get("estado_actual", "?")),
            str(contexto.get("estado_destino", "?")),
        )


def _guard_cancelacion(contexto: GuardaContext) -> None:
    """Guarda: no se permite cancelar un pedido ya despachado (ENVIADO o después)."""
    estado_actual = contexto.get("estado_actual")
    if estado_actual in (
        EstadoPedido.ENVIADO,
        EstadoPedido.ENTREGADO,
        EstadoPedido.ENTREGA_FALLIDA,
    ):
        raise CancelacionNoPermitidaError(str(estado_actual))


def _guard_guia(contexto: GuardaContext) -> None:
    """Guarda: se debe proporcionar una guía válida para despachar."""
    guia = contexto.get("guia")
    if not guia:
        raise TransicionEstadoInvalidaException(
            str(contexto.get("estado_actual", "?")),
            str(contexto.get("estado_destino", "?")),
        )


def _guard_devolucion(contexto: GuardaContext) -> None:
    """Guarda: solo se permite solicitar devolución para pedidos ENTREGADOS."""
    estado_actual = contexto.get("estado_actual")
    if estado_actual != EstadoPedido.ENTREGADO:
        raise DevolucionNoPermitidaError(str(estado_actual))


# Asociación de (estado_origen, estado_destino) -> callable guarda
GUARDAS: Dict[
    tuple[EstadoPedido, EstadoPedido], Callable[[GuardaContext], None]
] = {
    (EstadoPedido.PENDIENTE_PAGO, EstadoPedido.PAGADO): _guard_pagado,
    (EstadoPedido.PAGADO, EstadoPedido.EN_PREPARACION): _guard_preparacion,
    (EstadoPedido.EN_PREPARACION, EstadoPedido.EMPACADO): _guard_empacado,
    (EstadoPedido.CREADO, EstadoPedido.CANCELADO): _guard_cancelacion,
    (EstadoPedido.PENDIENTE_PAGO, EstadoPedido.CANCELADO): _guard_cancelacion,
    (EstadoPedido.PAGADO, EstadoPedido.CANCELADO): _guard_cancelacion,
    (EstadoPedido.EN_PREPARACION, EstadoPedido.CANCELADO): _guard_cancelacion,
    (EstadoPedido.EMPACADO, EstadoPedido.CANCELADO): _guard_cancelacion,
    (EstadoPedido.EMPACADO, EstadoPedido.ENVIADO): _guard_guia,
    (EstadoPedido.ENTREGADO, EstadoPedido.DEVUELTO): _guard_devolucion,
    (EstadoPedido.ENTREGA_FALLIDA, EstadoPedido.DEVUELTO): _guard_devolucion,
}


def transitar(
    estado_actual: EstadoPedido,
    estado_destino: EstadoPedido,
    contexto: GuardaContext | None = None,
) -> EstadoPedido:
    """Ejecuta una transición de estado, aplicando las guardas correspondientes.

    Lanza `TransicionEstadoInvalidaException` si la transición no está en la
    tabla de transiciones o si la guarda falla.
    """
    contexto = contexto or {}
    contexto.setdefault("estado_actual", estado_actual)
    contexto.setdefault("estado_destino", estado_destino)

    destinos = TRANSICIONES.get(estado_actual)
    if destinos is None or estado_destino not in destinos:
        raise TransicionEstadoInvalidaException(
            estado_actual.value, estado_destino.value
        )

    guarda = GUARDAS.get((estado_actual, estado_destino))
    if guarda is not None:
        guarda(contexto)

    return estado_destino