"""Modelos SQLAlchemy 2.0 (Declarative) para persistencia PostgreSQL.

Estos modelos están completamente separados de las entidades del dominio.
No hay lógica de negocio aquí; solo mapeo a tablas y relaciones.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos SQLAlchemy."""
    pass


class ClienteModel(Base):
    """Modelo de persistencia para Cliente."""
    __tablename__ = "clientes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    telefono: Mapped[str] = mapped_column(String(50), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    direcciones: Mapped[list["DireccionModel"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")
    pedidos: Mapped[list["PedidoModel"]] = relationship(back_populates="cliente")


class DireccionModel(Base):
    """Modelo de persistencia para DireccionEntrega (Value Object embebido)."""
    __tablename__ = "direcciones"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    cliente_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    calle: Mapped[str] = mapped_column(String(200), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    colonia: Mapped[str] = mapped_column(String(100), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    codigo_postal: Mapped[str] = mapped_column(String(5), nullable=False)

    cliente: Mapped["ClienteModel"] = relationship(back_populates="direcciones")


class ProductoModel(Base):
    """Modelo de persistencia para Producto."""
    __tablename__ = "productos"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # ej: SKU-00001
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    precio_monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    categoria: Mapped[str] = mapped_column(String(50), nullable=False)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)


class AlmacenModel(Base):
    """Modelo de persistencia para Almacen."""
    __tablename__ = "almacenes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ubicacion: Mapped[str] = mapped_column(String(200), nullable=False)

    existencias: Mapped[list["ExistenciaModel"]] = relationship(back_populates="almacen", cascade="all, delete-orphan")


class ExistenciaModel(Base):
    """Modelo de persistencia para ExistenciaProducto (stock en almacén)."""
    __tablename__ = "existencias"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    almacen_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("almacenes.id"), nullable=False)
    producto_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    cantidad_disponible: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cantidad_reservada: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    almacen: Mapped["AlmacenModel"] = relationship(back_populates="existencias")
    producto: Mapped["ProductoModel"] = relationship()

    __table_args__ = (
        UniqueConstraint("almacen_id", "sku", name="uq_almacen_sku"),
    )


class PedidoModel(Base):
    """Modelo de persistencia para Pedido (Aggregate Root)."""
    __tablename__ = "pedidos"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    cliente_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("clientes.id"), nullable=False)
    estado: Mapped[str] = mapped_column(SQLEnum("CREADO", "PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION", "EMPACADO", "ENVIADO", "ENTREGADO", "CANCELADO", "ENTREGA_FALLIDA", "DEVUELTO", name="estado_pedido_enum"), nullable=False, default="CREADO")
    direccion_calle: Mapped[str] = mapped_column(String(200), nullable=False)
    direccion_numero: Mapped[str] = mapped_column(String(20), nullable=False)
    direccion_colonia: Mapped[str] = mapped_column(String(100), nullable=False)
    direccion_ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    direccion_codigo_postal: Mapped[str] = mapped_column(String(5), nullable=False)
    reintentos_pago: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cliente: Mapped["ClienteModel"] = relationship(back_populates="pedidos")
    lineas: Mapped[list["LineaPedidoModel"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")
    surtidos: Mapped[list["SurtidoModel"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")
    pago: Mapped[Optional["PagoModel"]] = relationship(back_populates="pedido", uselist=False)
    envio: Mapped[Optional["EnvioModel"]] = relationship(back_populates="pedido", uselist=False)
    devolucion: Mapped[Optional["DevolucionModel"]] = relationship(back_populates="pedido", uselist=False)


class LineaPedidoModel(Base):
    """Modelo de persistencia para LineaPedido."""
    __tablename__ = "lineas_pedido"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    pedido_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario_monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_unitario_moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)

    pedido: Mapped["PedidoModel"] = relationship(back_populates="lineas")


class SurtidoModel(Base):
    """Modelo de persistencia para Surtido (Entity)."""
    __tablename__ = "surtidos"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    pedido_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False)
    almacen_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("almacenes.id"), nullable=False)
    estado: Mapped[str] = mapped_column(SQLEnum("PENDIENTE", "EN_PREPARACION", "EMPACADO", name="estado_surtido_enum"), nullable=False, default="PENDIENTE")

    pedido: Mapped["PedidoModel"] = relationship(back_populates="surtidos")
    almacen: Mapped["AlmacenModel"] = relationship()
    lineas: Mapped[list["LineaSurtidoModel"]] = relationship(back_populates="surtido", cascade="all, delete-orphan")


class LineaSurtidoModel(Base):
    """Modelo de persistencia para líneas del Surtido (relación N:M entre Surtido y Producto/SKU)."""
    __tablename__ = "lineas_surtido"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    surtido_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("surtidos.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario_monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    precio_unitario_moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)

    surtido: Mapped["SurtidoModel"] = relationship(back_populates="lineas")


class PagoModel(Base):
    """Modelo de persistencia para Pago."""
    __tablename__ = "pagos"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    pedido_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pedidos.id"), unique=True, nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(50), nullable=False)
    estado: Mapped[str] = mapped_column(SQLEnum("PENDIENTE", "APROBADO", "RECHAZADO", name="estado_pago_enum"), nullable=False, default="PENDIENTE")
    reintentos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    motivo_rechazo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaccion_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    pedido: Mapped["PedidoModel"] = relationship(back_populates="pago")


class EnvioModel(Base):
    """Modelo de persistencia para Envio."""
    __tablename__ = "envios"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    pedido_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pedidos.id"), unique=True, nullable=False)
    guia: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    estado: Mapped[str] = mapped_column(SQLEnum("PENDIENTE", "EN_TRASITO", "ENTREGADO", "FALLIDO", name="estado_envio_enum"), nullable=False, default="PENDIENTE")
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    pedido: Mapped["PedidoModel"] = relationship(back_populates="envio")
    intentos: Mapped[list["IntentoEntregaModel"]] = relationship(back_populates="envio", cascade="all, delete-orphan")


class IntentoEntregaModel(Base):
    """Modelo de persistencia para IntentoEntrega."""
    __tablename__ = "intentos_entrega"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    envio_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("envios.id"), nullable=False)
    exitoso: Mapped[bool] = mapped_column(nullable=False)
    numero_intento: Mapped[int] = mapped_column(Integer, nullable=False)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    envio: Mapped["EnvioModel"] = relationship(back_populates="intentos")


class DevolucionModel(Base):
    """Modelo de persistencia para Devolucion."""
    __tablename__ = "devoluciones"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    pedido_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pedidos.id"), unique=True, nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(SQLEnum("SOLICITADA", "APROBADA", "RECHAZADA", "PROCESADA", name="estado_devolucion_enum"), nullable=False, default="SOLICITADA")
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_autorizacion: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fecha_recepcion_almacen: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fecha_reembolso: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    motivo_rechazo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pedido: Mapped["PedidoModel"] = relationship(back_populates="devolucion")
    lineas: Mapped[list["LineaDevolucionModel"]] = relationship(back_populates="devolucion", cascade="all, delete-orphan")


class LineaDevolucionModel(Base):
    """Modelo de persistencia para LineaDevolucion."""
    __tablename__ = "lineas_devolucion"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    devolucion_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("devoluciones.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    devolucion: Mapped["DevolucionModel"] = relationship(back_populates="lineas")