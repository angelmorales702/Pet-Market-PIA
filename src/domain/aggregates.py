"""Aggregates (Raíces de Agregado) del dominio PetMarket.

Cada Aggregate Root encapsula la consistencia transaccional y las reglas de negocio
de su contexto. Se relacionan solo por identificadores (UUID).

Alineados con docs/fuentes/Diagrama_de_clases.md y Diagramas_DDD.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from .entities import (
    ExistenciaProducto,
    IntentoEntrega,
    LineaDevolucion,
    LineaPedido,
    Surtido,
)
from .events import (
    DevolucionAprobadaEvent,
    DevolucionSolicitadaEvent,
    DiscrepanciaInventarioDetectadaEvent,
    EntregaFallidaEvent,
    IntentoEntregaRegistradoEvent,
    PagoAprobadoEvent,
    PagoRechazadoEvent,
    PedidoCanceladoEvent,
    PedidoCreadoEvent,
    PedidoEmpacadoEvent,
    PedidoEntregadoEvent,
    PedidoEnviadoEvent,
    StockInsuficienteEvent,
    StockReservadoEvent,
    SurtidoEmpacadoEvent,
)
from .exceptions import (
    CancelacionNoPermitidaError,
    DevolucionNoPermitidaError,
    PagoMontoNoCoincideError,
    PagoRechazadoError,
    StockInsuficienteError,
    TransicionEstadoInvalidaException,
)
from .state_machine import EstadoPedido, transitar
from .value_objects import (
    DireccionEntrega,
    Dinero,
    EstadoDevolucion,
    EstadoEnvio,
    EstadoPago,
    Guia,
    MotivoDevolucion,
    Sku,
)


class AggregateRoot:
    """Clase base para Aggregate Roots con manejo de Domain Events."""
    _domain_events: list

    def __init__(self) -> None:
        self._domain_events = []

    @property
    def domain_events(self) -> list:
        return self._domain_events

    def add_domain_event(self, event) -> None:
        self._domain_events.append(event)

    def clear_domain_events(self) -> list:
        events = self._domain_events
        self._domain_events = []
        return events

    def __post_init__(self) -> None:
        """Llamado por dataclass después de __init__."""
        if not hasattr(self, '_domain_events') or self._domain_events is None:
            self._domain_events = []


# ============================================================================
# AGREGADO: Pedido (Aggregate Root principal)
# ============================================================================

@dataclass
class Pedido(AggregateRoot):
    """Aggregate Root: Pedido.

    Gestiona el ciclo de vida del pedido, sus líneas, surtidos y transiciones de estado.
    Emite Domain Events en cada cambio de estado relevante.
    """
    id: UUID
    cliente_id: UUID
    lineas: list[LineaPedido]
    direccion_entrega: DireccionEntrega
    estado: EstadoPedido = EstadoPedido.CREADO
    surtidos: list[Surtido] = field(default_factory=list)
    _pago_id: Optional[UUID] = None
    _envio_id: Optional[UUID] = None
    _devolucion_id: Optional[UUID] = None
    reintentos_pago: int = 0
    fecha_creacion: datetime = field(default_factory=datetime.now)
    fecha_actualizacion: datetime = field(default_factory=datetime.now)

    @classmethod
    def crear(
        cls,
        cliente_id: UUID,
        lineas: list[LineaPedido],
        direccion_entrega: DireccionEntrega,
    ) -> "Pedido":
        """Crea un nuevo pedido en estado CREADO.

        US-004: Compra confirmada tras pago exitoso.
        """
        if not lineas:
            raise ValueError("El pedido debe tener al menos una línea")
        pedido = cls(
            id=uuid4(),
            cliente_id=cliente_id,
            lineas=lineas,
            direccion_entrega=direccion_entrega,
            estado=EstadoPedido.CREADO,
        )
        pedido.add_domain_event(PedidoCreadoEvent(pedido_id=pedido.id, cliente_id=cliente_id))
        return pedido

    def asignar_surtidos(self, surtidos: list[Surtido]) -> None:
        """Asigna los surtidos al pedido (resultado de AsignacionAlmacenService).

        ADR-002: El pedido se divide en Surtidos por almacén.
        """
        self.surtidos = surtidos
        for surtido in surtidos:
            surtido.pedido_id = self.id
        self.estado = EstadoPedido.PENDIENTE_PAGO
        self.fecha_actualizacion = datetime.now()

    def marcar_pagado(self, monto_pagado: Dinero) -> None:
        """Marca el pedido como pagado tras confirmación de pago.

        US-003, US-004
        """
        self._transicionar(EstadoPedido.PAGADO, {"pagado": monto_pagado, "total": self.total})
        self.add_domain_event(PagoAprobadoEvent(
            pedido_id=self.id,
            monto=str(monto_pagado.monto),
            moneda=monto_pagado.moneda,
        ))
        # Confirmar reservas en almacenes (descuenta stock real)
        for surtido in self.surtidos:
            for linea in surtido.lineas:
                # Se haría via Almacen en la capa de aplicación
                pass

    def marcar_pago_rechazado(self, motivo: str) -> None:
        """Marca el pago como rechazado e incrementa reintentos.

        US-003: Hasta 3 reintentos de pago.
        """
        self.reintentos_pago += 1
        if self.reintentos_pago >= 3:
            self.cancelar("Pago rechazado tras 3 intentos")
            self.add_domain_event(PagoRechazadoEvent(
                pedido_id=self.id,
                monto=str(self.total.monto),
                moneda=self.total.moneda,
                motivo=f"{motivo} (3 reintentos agotados)",
            ))
        else:
            self.add_domain_event(PagoRechazadoEvent(
                pedido_id=self.id,
                monto=str(self.total.monto),
                moneda=self.total.moneda,
                motivo=motivo,
            ))
        self.fecha_actualizacion = datetime.now()

    def iniciar_preparacion(self) -> None:
        """Inicia la preparación del pedido (transición a EN_PREPARACION).

        US-007: Almacén recibe pedido para empaquetado.
        """
        self._transicionar(EstadoPedido.EN_PREPARACION)
        for surtido in self.surtidos:
            surtido.marcar_en_preparacion()
        self.fecha_actualizacion = datetime.now()

    def confirmar_empaque(self, almacen_id: UUID) -> None:
        """Confirma el empaque de un surtido específico.

        US-007: Operador realiza picking y empaquetado.
        """
        surtido = next((s for s in self.surtidos if s.almacen_id == almacen_id), None)
        if not surtido:
            from .exceptions import SurtidoNoEncontradoError
            raise SurtidoNoEncontradoError(str(almacen_id))
        surtido.marcar_empacado()
        self.add_domain_event(SurtidoEmpacadoEvent(
            pedido_id=self.id,
            surtido_id=surtido.id,
        ))
        # Verificar si todos los surtidos están empacados
        if all(s.estado.value == "EMPACADO" for s in self.surtidos):
            self._transicionar(EstadoPedido.EMPACADO, {"surtidos": self.surtidos})
            self.add_domain_event(PedidoEmpacadoEvent(pedido_id=self.id))
        self.fecha_actualizacion = datetime.now()

    def marcar_enviado(self, guia: Guia) -> None:
        """Marca el pedido como enviado asignando la guía.

        US-006: Envíos separados por almacén, un solo número de pedido.
        """
        self._transicionar(EstadoPedido.ENVIADO, {"guia": guia})
        self.add_domain_event(PedidoEnviadoEvent(pedido_id=self.id, guia=guia.valor))
        self.fecha_actualizacion = datetime.now()

    def registrar_intento_entrega(self, exitoso: bool, observaciones: str = "") -> None:
        """Registra un intento de entrega.

        US-010, US-011: Máximo 2 intentos de entrega.
        """
        # La lógica de intentos y estado se delega a la entidad Envio
        # Aquí solo emitimos el evento
        numero_intento = 1  # Se obtendría del Envio en la capa de aplicación
        self.add_domain_event(IntentoEntregaRegistradoEvent(
            pedido_id=self.id,
            exitoso=exitoso,
            numero_intento=numero_intento,
        ))
        if exitoso:
            self._transicionar(EstadoPedido.ENTREGADO)
            self.add_domain_event(PedidoEntregadoEvent(pedido_id=self.id))
        self.fecha_actualizacion = datetime.now()

    def marcar_entrega_fallida(self) -> None:
        """Marca la entrega como fallida tras agotar intentos.

        US-011: Segundo intento fallido -> regresa a almacén.
        """
        self._transicionar(EstadoPedido.ENTREGA_FALLIDA)
        self.add_domain_event(EntregaFallidaEvent(
            pedido_id=self.id,
            intentos_realizados=2,
        ))
        self.fecha_actualizacion = datetime.now()

    def solicitar_devolucion(self, motivo: MotivoDevolucion) -> UUID:
        """Solicita una devolución para el pedido entregado.

        US-013: Ventana de 5 días hábiles.
        US-014: Atención al cliente autoriza, Almacén confirma recepción.
        """
        if self.estado != EstadoPedido.ENTREGADO:
            raise DevolucionNoPermitidaError(self.estado.value)
        devolucion_id = uuid4()
        self._devolucion_id = devolucion_id
        self.add_domain_event(DevolucionSolicitadaEvent(
            pedido_id=self.id,
            devolucion_id=devolucion_id,
            motivo=motivo.valor,
        ))
        self.fecha_actualizacion = datetime.now()
        return devolucion_id

    def cancelar(self, motivo: str) -> None:
        """Cancela el pedido si el estado lo permite.

        US-008: Cancelación antes de preparación sin penalización.
        US-009: Cancelación tardía requiere autorización de Atención al cliente.
        """
        # La guarda en state_machine verifica que no esté ENVIADO o posterior
        self._transicionar(EstadoPedido.CANCELADO)
        self.add_domain_event(PedidoCanceladoEvent(pedido_id=self.id))
        self.fecha_actualizacion = datetime.now()

    @property
    def total(self) -> Dinero:
        """Monto total del pedido."""
        total = Dinero(0, "MXN")
        for linea in self.lineas:
            subtotal = Dinero(linea.precio_unitario.monto * linea.cantidad, linea.precio_unitario.moneda)
            total = total + subtotal
        return total

    def _transicionar(self, nuevo_estado: EstadoPedido, contexto: dict | None = None) -> None:
        """Realiza la transición de estado usando la State Machine."""
        self.estado = transitar(self.estado, nuevo_estado, contexto)
        self.fecha_actualizacion = datetime.now()

    def puede_cancelar_cliente(self) -> bool:
        """US-008: Cliente puede cancelar solo antes de EN_PREPARACION."""
        return self.estado in (EstadoPedido.CREADO, EstadoPedido.PENDIENTE_PAGO, EstadoPedido.PAGADO)


# ============================================================================
# AGREGADO: Cliente
# ============================================================================

@dataclass
class Cliente(AggregateRoot):
    """Aggregate Root: Cliente.

    Información del cliente que realiza pedidos.
    """
    id: UUID
    nombre: str
    email: str
    telefono: str
    direcciones: list[DireccionEntrega] = field(default_factory=list)

    @classmethod
    def crear(cls, nombre: str, email: str, telefono: str) -> "Cliente":
        if not nombre or not email:
            raise ValueError("Nombre y email son obligatorios")
        return cls(
            id=uuid4(),
            nombre=nombre,
            email=email,
            telefono=telefono,
        )

    def agregar_direccion(self, direccion: DireccionEntrega) -> None:
        self.direcciones.append(direccion)


# ============================================================================
# AGREGADO: Producto
# ============================================================================

@dataclass
class Producto(AggregateRoot):
    """Aggregate Root: Producto.

    Catálogo de productos disponibles para venta.
    """
    id: UUID
    sku: Sku
    nombre: str
    descripcion: str
    precio: Dinero
    categoria: str  # "Alimentos", "Accesorios", "Higiene", "Otros"
    activo: bool = True

    @classmethod
    def crear(cls, sku: Sku, nombre: str, descripcion: str, precio: Dinero, categoria: str) -> "Producto":
        return cls(
            id=uuid4(),
            sku=sku,
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            categoria=categoria,
            activo=True,
        )

    def actualizar_precio(self, nuevo_precio: Dinero) -> None:
        self.precio = nuevo_precio

    def desactivar(self) -> None:
        self.activo = False


# ============================================================================
# AGREGADO: Almacen
# ============================================================================

@dataclass
class Almacen(AggregateRoot):
    """Aggregate Root: Almacen.

    Gestiona existencias y reservas de productos.
    """
    id: UUID
    nombre: str  # "Norte" o "Sur"
    ubicacion: str
    existencias: dict[str, ExistenciaProducto] = field(default_factory=dict)  # key: sku

    @classmethod
    def crear(cls, nombre: str, ubicacion: str) -> "Almacen":
        return cls(id=uuid4(), nombre=nombre, ubicacion=ubicacion)

    def obtener_existencia(self, sku: Sku) -> Optional[ExistenciaProducto]:
        return self.existencias.get(str(sku))

    def agregar_existencia(self, producto_id: UUID, sku: Sku, cantidad: int) -> ExistenciaProducto:
        ex = ExistenciaProducto(
            producto_id=producto_id,
            almacen_id=self.id,
            sku=sku,
            cantidad_disponible=cantidad,
        )
        self.existencias[str(sku)] = ex
        return ex

    def reservar(self, sku: Sku, cantidad: int, pedido_id: UUID) -> None:
        """Reserva stock para un pedido.

        US-001, US-002: Reserva de 15 minutos durante checkout.
        """
        ex = self.obtener_existencia(sku)
        if not ex:
            raise StockInsuficienteError(str(sku), cantidad, 0)
        ex.reservar(cantidad)
        self.add_domain_event(StockReservadoEvent(
            pedido_id=pedido_id,
            almacen_id=self.id,
            sku=str(sku),
            cantidad=cantidad,
        ))

    def liberar_reserva(self, sku: Sku, cantidad: int) -> None:
        """Libera reserva (pago rechazado o expiración)."""
        ex = self.obtener_existencia(sku)
        if ex:
            ex.liberar_reserva(cantidad)

    def confirmar_venta(self, sku: Sku, cantidad: int) -> None:
        """Confirma la venta (pago aprobado -> descuenta stock real)."""
        ex = self.obtener_existencia(sku)
        if ex:
            ex.confirmar_reserva(cantidad)

    def detectar_discrepancia(self, sku: Sku, cantidad_fisica: int) -> None:
        """US-016: Detecta discrepancia entre inventario web y físico."""
        ex = self.obtener_existencia(sku)
        cantidad_web = ex.cantidad_disponible if ex else 0
        if cantidad_web != cantidad_fisica:
            self.add_domain_event(DiscrepanciaInventarioDetectadaEvent(
                almacen_id=self.id,
                sku=str(sku),
                diferencia=cantidad_fisica - cantidad_web,
            ))


# ============================================================================
# AGREGADO: Pago
# ============================================================================

@dataclass
class Pago(AggregateRoot):
    """Aggregate Root: Pago.

    Gestiona el estado del pago de un pedido.
    """
    id: UUID
    pedido_id: UUID
    monto: Dinero
    metodo_pago: str  # "tarjeta", "transferencia", "efectivo"
    estado: EstadoPago = EstadoPago.PENDIENTE
    reintentos: int = 0
    motivo_rechazo: Optional[str] = None
    fecha_creacion: datetime = field(default_factory=datetime.now)
    fecha_actualizacion: datetime = field(default_factory=datetime.now)

    @classmethod
    def crear(cls, pedido_id: UUID, monto: Dinero, metodo_pago: str) -> "Pago":
        return cls(
            id=uuid4(),
            pedido_id=pedido_id,
            monto=monto,
            metodo_pago=metodo_pago,
            estado=EstadoPago.PENDIENTE,
        )

    def aprobar(self) -> None:
        """Aprueba el pago.

        Diagrama_de_clases.md: +aprobar()
        """
        if self.estado != EstadoPago.PENDIENTE:
            raise TransicionEstadoInvalidaException(self.estado.value, EstadoPago.APROBADO.value)
        self.estado = EstadoPago.APROBADO
        self.fecha_actualizacion = datetime.now()

    def rechazar(self, motivo: str) -> None:
        """Rechaza el pago e incrementa reintentos.

        US-003: Máximo 3 reintentos.
        """
        self.reintentos += 1
        self.motivo_rechazo = motivo
        self.fecha_actualizacion = datetime.now()
        if self.reintentos >= 3:
            self.estado = EstadoPago.RECHAZADO

    def reembolsar(self) -> None:
        """Procesa reembolso (tras devolución confirmada).

        US-015: Reembolso tras confirmación de Almacén.
        """
        if self.estado != EstadoPago.APROBADO:
            raise TransicionEstadoInvalidaException(self.estado.value, "REEMBOLSADO")
        self.estado = EstadoPago.RECHAZADO  # En este modelo, RECHAZADO sirve como "reembolsado"
        # # SUPUESTO: Añadir estado REEMBOLSADO explícito. Validar con el negocio.
        self.fecha_actualizacion = datetime.now()


# ============================================================================
# AGREGADO: Envio
# ============================================================================

@dataclass
class Envio(AggregateRoot):
    """Aggregate Root: Envio.

    Gestiona el envío y los intentos de entrega.
    """
    id: UUID
    pedido_id: UUID
    guia: Optional[Guia] = None
    estado: EstadoEnvio = EstadoEnvio.PENDIENTE
    intentos: list[IntentoEntrega] = field(default_factory=list)
    fecha_creacion: datetime = field(default_factory=datetime.now)
    fecha_actualizacion: datetime = field(default_factory=datetime.now)

    @classmethod
    def crear(cls, pedido_id: UUID) -> "Envio":
        return cls(id=uuid4(), pedido_id=pedido_id)

    def asignar_guia(self, guia: Guia) -> None:
        """Asigna la guía de envío y pasa a EN_TRASITO.

        US-006: Envíos separados por almacén, un solo número de pedido.
        """
        self.guia = guia
        self.estado = EstadoEnvio.EN_TRASITO
        self.fecha_actualizacion = datetime.now()

    def registrar_intento(self, exitoso: bool, observaciones: str = "") -> IntentoEntrega:
        """Registra un intento de entrega.

        US-010, US-011: Máximo 2 intentos.
        """
        numero = len(self.intentos) + 1
        intento = IntentoEntrega(
            id=uuid4(),
            envio_id=self.id,
            exitoso=exitoso,
            numero_intento=numero,
            observaciones=observaciones,
        )
        self.intentos.append(intento)
        self.fecha_actualizacion = datetime.now()

        if exitoso:
            self.estado = EstadoEnvio.ENTREGADO
        elif numero >= 2:
            # Segundo intento fallido -> regresa a almacén
            self.estado = EstadoEnvio.FALLIDO

        return intento

    def get_intentos_realizados(self) -> int:
        return len(self.intentos)


# ============================================================================
# AGREGADO: Devolucion
# ============================================================================

@dataclass
class Devolucion(AggregateRoot):
    """Aggregate Root: Devolucion.

    Gestiona el proceso de devolución y reembolso.

    US-013: Ventana de 5 días hábiles.
    US-014: Atención al cliente autoriza, Almacén confirma recepción.
    US-015: Pagos procesa reembolso.
    """
    id: UUID
    pedido_id: UUID
    lineas: list[LineaDevolucion]
    motivo: MotivoDevolucion
    estado: EstadoDevolucion = EstadoDevolucion.SOLICITADA
    fecha_solicitud: datetime = field(default_factory=datetime.now)
    fecha_autorizacion: Optional[datetime] = None
    fecha_recepcion_almacen: Optional[datetime] = None
    fecha_reembolso: Optional[datetime] = None

    @classmethod
    def solicitar(cls, pedido_id: UUID, lineas: list[LineaDevolucion], motivo: MotivoDevolucion) -> "Devolucion":
        return cls(
            id=uuid4(),
            pedido_id=pedido_id,
            lineas=lineas,
            motivo=motivo,
            estado=EstadoDevolucion.SOLICITADA,
        )

    def autorizar(self) -> None:
        """Atención al cliente autoriza la devolución.

        US-014: Atención al cliente autoriza -> indica al cliente cómo regresar.
        """
        if self.estado != EstadoDevolucion.SOLICITADA:
            raise TransicionEstadoInvalidaException(self.estado.value, EstadoDevolucion.APROBADA.value)
        self.estado = EstadoDevolucion.APROBADA
        self.fecha_autorizacion = datetime.now()
        self.add_domain_event(DevolucionAprobadaEvent(
            pedido_id=self.pedido_id,
            devolucion_id=self.id,
        ))

    def rechazar(self, motivo: str) -> None:
        """Atención al cliente rechaza la devolución."""
        if self.estado != EstadoDevolucion.SOLICITADA:
            raise TransicionEstadoInvalidaException(self.estado.value, EstadoDevolucion.RECHAZADA.value)
        self.estado = EstadoDevolucion.RECHAZADA
        # # SUPUESTO: Guardar motivo de rechazo. Validar con el negocio.

    def confirmar_recepcion_almacen(self) -> None:
        """Almacén confirma recepción física del producto devuelto.

        US-014: Almacén confirma recepción -> libera reembolso a Pagos.
        """
        if self.estado != EstadoDevolucion.APROBADA:
            raise TransicionEstadoInvalidaException(self.estado.value, EstadoDevolucion.PROCESADA.value)
        self.estado = EstadoDevolucion.PROCESADA
        self.fecha_recepcion_almacen = datetime.now()

    def marcar_reembolsado(self) -> None:
        """Pagos procesa el reembolso.

        US-015: Reembolso procesado -> notifica cliente y cierra pedido.
        """
        if self.estado != EstadoDevolucion.PROCESADA:
            raise TransicionEstadoInvalidaException(self.estado.value, "REEMBOLSADO")
        self.fecha_reembolso = datetime.now()

    def esta_dentro_ventana(self, fecha_entrega: datetime, dias_habiles: int = 5) -> bool:
        """Verifica si la solicitud está dentro de la ventana de devolución.

        US-013: 5 días hábiles posteriores a la entrega.
        # SUPUESTO: Cálculo de días hábiles (excluye fines de semana). Validar con el negocio.
        """
        fecha_limite = fecha_entrega
        dias_agregados = 0
        while dias_agregados < dias_habiles:
            fecha_limite += timedelta(days=1)
            if fecha_limite.weekday() < 5:  # 0-4 = Lun-Vie
                dias_agregados += 1
        return datetime.now() <= fecha_limite