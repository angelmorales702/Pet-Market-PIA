"""Casos de Uso (Application Services) - PetMarket.

Implementa los casos de uso del sistema siguiendo Clean Architecture y DDD.
Cada caso de uso está documentado con su US-xxx correspondiente.

Orquestan:
1. Cargan agregados usando repositorios (via Unit of Work).
2. Invocan métodos de negocio en los agregados / servicios de dominio.
3. Persisten los cambios.
4. Recogen y publican Domain Events (ADR-003).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from src.domain.aggregates import Almacen, Devolucion, Envio, Pago, Pedido
from src.domain.entities import LineaDevolucion, LineaPedido
from src.domain.services import AsignacionAlmacenService, CalendarioDiasHabiles, Reloj
from src.domain.value_objects import DireccionEntrega, Dinero, Guia, MotivoDevolucion, Sku
from .ports import (
    PasarelaPago,
    PublicadorEventos,
    UnitOfWork,
)


class ConfirmarCheckoutUseCase:
    """US-001, US-002, US-006: Crea el pedido, asigna surtidos por almacén, reserva stock y genera PENDIENTE_PAGO."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos, reloj: Optional[Reloj] = None):
        self._uow = uow
        self._publisher = event_publisher
        self._asignador = AsignacionAlmacenService(reloj=reloj)

    def ejecutar(self, cliente_id: UUID, lineas: list[LineaPedido], direccion: DireccionEntrega) -> Pedido:
        with self._uow as uow:
            # 1. Obtener todos los almacenes
            almacenes = uow.almacenes.obtener_todos()
            if not almacenes:
                raise ValueError("No hay almacenes configurados en el sistema")

            # 2. Crear pedido en estado CREADO
            pedido = Pedido.crear(cliente_id=cliente_id, lineas=lineas, direccion_entrega=direccion)

            # 3. Asignar surtidos (reserva stock automáticamente vía servicio de dominio)
            surtidos = self._asignador.asignar(pedido, almacenes, reservar=True)
            pedido.asignar_surtidos(surtidos)

            # 4. Guardar pedido, surtidos y almacenes actualizados
            uow.pedidos.guardar(pedido)
            for surtido in surtidos:
                uow.surtidos.guardar(surtido)
            for almacen in almacenes:
                uow.almacenes.guardar(almacen)

            # 5. Publicar eventos de dominio (ADR-003)
            eventos = pedido.clear_domain_events()
            for almacen in almacenes:
                eventos.extend(almacen.clear_domain_events())
            self._publisher.publicar(eventos)

            uow.commit()
            return pedido


class ProcesarPagoUseCase:
    """US-003, US-004: Procesa el pago de un pedido con reintentos y pasarela externa."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos, pasarela: PasarelaPago):
        self._uow = uow
        self._publisher = event_publisher
        self._pasarela = pasarela

    def ejecutar(self, pedido_id: UUID, metodo_pago: str, datos_cliente: dict) -> Pago:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")

            total = pedido.total
            pago = Pago.crear(pedido_id=pedido.id, monto=total, metodo_pago=metodo_pago)

            # Invocar pasarela de pago externa
            resultado = self._pasarela.cobrar(monto=total, metodo_pago=metodo_pago, datos_cliente=datos_cliente)

            if resultado.aprobado:
                pago.aprobar()
                pedido.marcar_pagado(total)
                # Confirmar reservas de stock en almacenes
                almacenes = uow.almacenes.obtener_todos()
                for surtido in pedido.surtidos:
                    almacen = next((a for a in almacenes if a.id == surtido.almacen_id), None)
                    if almacen:
                        for linea in surtido.lineas:
                            almacen.confirmar_venta(linea.sku, linea.cantidad)
                        uow.almacenes.guardar(almacen)
            else:
                motivo = resultado.motivo or "Pago rechazado por pasarela"
                pago.rechazar(motivo)
                pedido.marcar_pago_rechazado(motivo)
                # Si se canceló por 3 reintentos, liberar reservas en almacenes
                if pedido.estado.value == "CANCELADO":
                    almacenes = uow.almacenes.obtener_todos()
                    for surtido in pedido.surtidos:
                        almacen = next((a for a in almacenes if a.id == surtido.almacen_id), None)
                        if almacen:
                            for linea in surtido.lineas:
                                almacen.liberar_reserva(linea.sku, linea.cantidad)
                            uow.almacenes.guardar(almacen)

            uow.pagos.guardar(pago)
            uow.pedidos.guardar(pedido)

            eventos = pedido.clear_domain_events()
            eventos.extend(pago.clear_domain_events())
            self._publisher.publicar(eventos)

            uow.commit()
            return pago


class ExpirarReservasUseCase:
    """US-002: Libera reservas de stock expiradas (15 min sin pago)."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos):
        self._uow = uow
        self._publisher = event_publisher

    def ejecutar(self, pedido_id: UUID) -> None:
        """Expira la reserva de un pedido no pagado a los 15 minutos."""
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido or pedido.estado.value != "PENDIENTE_PAGO":
                return

            pedido.cancelar("Reserva expirada por tiempo (15 min sin pago)")

            almacenes = uow.almacenes.obtener_todos()
            for surtido in pedido.surtidos:
                almacen = next((a for a in almacenes if a.id == surtido.almacen_id), None)
                if almacen:
                    for linea in surtido.lineas:
                        almacen.liberar_reserva(linea.sku, linea.cantidad)
                    uow.almacenes.guardar(almacen)

            uow.pedidos.guardar(pedido)
            eventos = pedido.clear_domain_events()
            self._publisher.publicar(eventos)
            uow.commit()


class CancelarPedidoUseCase:
    """US-008, US-009: Cancela un pedido. Si está en preparación o posterior, requiere autorización."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos):
        self._uow = uow
        self._publisher = event_publisher

    def ejecutar(self, pedido_id: UUID, motivo: str, autorizado_por_atencion: bool = False) -> Pedido:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")

            # US-009: Cancelación tardía requiere autorización
            if not pedido.puede_cancelar_cliente() and not autorizado_por_atencion:
                from src.domain.exceptions import CancelacionNoPermitidaError
                raise CancelacionNoPermitidaError(pedido.estado.value)

            pedido.cancelar(motivo)

            # Liberar stock reservado o inventario si ya estaba pagado/en preparación
            almacenes = uow.almacenes.obtener_todos()
            for surtido in pedido.surtidos:
                almacen = next((a for a in almacenes if a.id == surtido.almacen_id), None)
                if almacen:
                    for linea in surtido.lineas:
                        # Si estaba pagado, el stock ya se descontó, habría que reingresarlo o liberar reserva
                        almacen.liberar_reserva(linea.sku, linea.cantidad)
                    uow.almacenes.guardar(almacen)

            uow.pedidos.guardar(pedido)
            eventos = pedido.clear_domain_events()
            self._publisher.publicar(eventos)
            uow.commit()
            return pedido


class IniciarYEmpacarSurtidoUseCase:
    """US-007: Inicia preparación y empaca un surtido de almacén."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos):
        self._uow = uow
        self._publisher = event_publisher

    def iniciar_preparacion(self, pedido_id: UUID) -> Pedido:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")
            pedido.iniciar_preparacion()
            uow.pedidos.guardar(pedido)
            for surtido in pedido.surtidos:
                uow.surtidos.guardar(surtido)
            eventos = pedido.clear_domain_events()
            self._publisher.publicar(eventos)
            uow.commit()
            return pedido

    def confirmar_empaque_surtido(self, pedido_id: UUID, almacen_id: UUID) -> Pedido:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")
            pedido.confirmar_empaque(almacen_id)
            uow.pedidos.guardar(pedido)
            for surtido in pedido.surtidos:
                uow.surtidos.guardar(surtido)
            eventos = pedido.clear_domain_events()
            self._publisher.publicar(eventos)
            uow.commit()
            return pedido


class DespacharPedidoUseCase:
    """US-006: Despacha el pedido generando el Envío y la Guía."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos):
        self._uow = uow
        self._publisher = event_publisher

    def ejecutar(self, pedido_id: UUID, codigo_guia: str) -> Envio:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")

            guia = Guia.of(codigo_guia)
            pedido.marcar_enviado(guia)

            envio = Envio.crear(pedido_id=pedido.id)
            envio.asignar_guia(guia)

            uow.pedidos.guardar(pedido)
            uow.envios.guardar(envio)

            eventos = pedido.clear_domain_events()
            eventos.extend(envio.clear_domain_events())
            self._publisher.publicar(eventos)
            uow.commit()
            return envio


class RegistrarEntregaUseCase:
    """US-010, US-011: Registra un intento de entrega (exitoso o fallido)."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos):
        self._uow = uow
        self._publisher = event_publisher

    def ejecutar(self, pedido_id: UUID, exitoso: bool, observaciones: str = "") -> Envio:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")

            envio = uow.envios.obtener_por_pedido(pedido_id)
            if not envio:
                envio = Envio.crear(pedido_id=pedido.id)

            intento = envio.registrar_intento(exitoso=exitoso, observaciones=observaciones)

            if exitoso:
                pedido.registrar_intento_entrega(exitoso=True, observaciones=observaciones)
            elif envio.estado.value == "FALLIDO":
                pedido.marcar_entrega_fallida()
            else:
                pedido.registrar_intento_entrega(exitoso=False, observaciones=observaciones)

            uow.pedidos.guardar(pedido)
            uow.envios.guardar(envio)

            eventos = pedido.clear_domain_events()
            eventos.extend(envio.clear_domain_events())
            self._publisher.publicar(eventos)
            uow.commit()
            return envio


class SolicitarDevolucionUseCase:
    """US-013, US-014: Solicita una devolución dentro de la ventana de 5 días hábiles."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos, calendario: Optional[CalendarioDiasHabiles] = None):
        self._uow = uow
        self._publisher = event_publisher
        self._calendario = calendario

    def ejecutar(self, pedido_id: UUID, lineas: list[LineaDevolucion], motivo: MotivoDevolucion, fecha_entrega: datetime) -> Devolucion:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")

            devolucion = Devolucion.solicitar(pedido_id=pedido.id, lineas=lineas, motivo=motivo)

            # Verificar ventana de 5 días hábiles
            if not devolucion.esta_dentro_ventana(fecha_entrega):
                raise DevolucionNoPermitidaError("Fuera de la ventana de 5 días hábiles")

            pedido_devolucion_id = pedido.solicitar_devolucion(motivo)

            uow.pedidos.guardar(pedido)
            uow.devoluciones.guardar(devolucion)

            eventos = pedido.clear_domain_events()
            eventos.extend(devolucion.clear_domain_events())
            self._publisher.publicar(eventos)
            uow.commit()
            return devolucion


class AutorizarDevolucionUseCase:
    """US-014: Atención al cliente autoriza la devolución."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos):
        self._uow = uow
        self._publisher = event_publisher

    def autorizar(self, devolucion_id: UUID) -> Devolucion:
        with self._uow as uow:
            devolucion = uow.devoluciones.obtener_por_id(devolucion_id)
            if not devolucion:
                raise ValueError(f"Devolución {devolucion_id} no encontrada")
            devolucion.autorizar()
            uow.devoluciones.guardar(devolucion)
            eventos = devolucion.clear_domain_events()
            self._publisher.publicar(eventos)
            uow.commit()
            return devolucion

    def rechazar(self, devolucion_id: UUID, motivo: str) -> Devolucion:
        with self._uow as uow:
            devolucion = uow.devoluciones.obtener_por_id(devolucion_id)
            if not devolucion:
                raise ValueError(f"Devolución {devolucion_id} no encontrada")
            devolucion.rechazar(motivo)
            uow.devoluciones.guardar(devolucion)
            eventos = devolucion.clear_domain_events()
            self._publisher.publicar(eventos)
            uow.commit()
            return devolucion


class ProcesarReembolsoUseCase:
    """US-015: Almacén confirma recepción y Pagos procesa el reembolso."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos, pasarela: PasarelaPago):
        self._uow = uow
        self._publisher = event_publisher
        self._pasarela = pasarela

    def confirmar_recepcion_y_reembolsar(self, devolucion_id: UUID) -> Devolucion:
        with self._uow as uow:
            devolucion = uow.devoluciones.obtener_por_id(devolucion_id)
            if not devolucion:
                raise ValueError(f"Devolución {devolucion_id} no encontrada")

            devolucion.confirmar_recepcion_almacen()

            pago = uow.pagos.obtener_por_pedido(devolucion.pedido_id)
            if pago:
                resultado = self._pasarela.reembolsar("TRANS_REF", pago.monto)
                if resultado.aprobado:
                    pago.reembolsar()
                    uow.pagos.guardar(pago)

            devolucion.marcar_reembolsado()
            uow.devoluciones.guardar(devolucion)

            eventos = devolucion.clear_domain_events()
            if pago:
                eventos.extend(pago.clear_domain_events())
            self._publisher.publicar(eventos)
            uow.commit()
            return devolucion


class ConsultarEstadoPedidoUseCase:
    """Consulta el estado actual de un pedido y sus surtidos/envíos."""

    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    def ejecutar(self, pedido_id: UUID) -> dict:
        with self._uow as uow:
            pedido = uow.pedidos.obtener_por_id(pedido_id)
            if not pedido:
                raise ValueError(f"Pedido {pedido_id} no encontrado")
            envio = uow.envios.obtener_por_pedido(pedido_id)
            pago = uow.pagos.obtener_por_pedido(pedido_id)
            return {
                "pedido_id": str(pedido.id),
                "estado": pedido.estado.value,
                "total": {
                    "monto": str(pedido.total.monto),
                    "moneda": pedido.total.moneda,
                },
                "surtidos": [
                    {
                        "surtido_id": str(s.id),
                        "almacen_id": str(s.almacen_id),
                        "estado": s.estado.value,
                        "lineas": [{"sku": str(l.sku), "cantidad": l.cantidad} for l in s.lineas],
                    }
                    for s in pedido.surtidos
                ],
                "envio_estado": envio.estado.value if envio else "SIN_ENVIO",
                "pago_estado": pago.estado.value if pago else "SIN_PAGO",
            }


class ConsultarDiscrepanciaInventarioUseCase:
    """US-016: Detecta y registra discrepancia de inventario web vs físico."""

    def __init__(self, uow: UnitOfWork, event_publisher: PublicadorEventos):
        self._uow = uow
        self._publisher = event_publisher

    def ejecutar(self, almacen_id: UUID, sku: Sku, cantidad_fisica: int) -> None:
        with self._uow as uow:
            almacen = uow.almacenes.obtener_por_id(almacen_id)
            if not almacen:
                raise ValueError(f"Almacén {almacen_id} no encontrado")
            almacen.detectar_discrepancia(sku, cantidad_fisica)
            uow.almacenes.guardar(almacen)
            eventos = almacen.clear_domain_events()
            self._publisher.publicar(eventos)
            uow.commit()