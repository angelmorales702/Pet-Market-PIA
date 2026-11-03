"""Schemas Pydantic para request/response de la API.

Definen los contratos de entrada y salida de los endpoints.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from src.domain.aggregates import Almacen, Cliente, Devolucion, Envio, Pago, Pedido, Producto
from src.domain.entities import LineaPedido, LineaDevolucion, Surtido
from src.domain.value_objects import DireccionEntrega, Dinero, Guia, Sku, MotivoDevolucion


# =============================================================================
# Schemas para Productos (Catálogo)
# =============================================================================

class ProductoSchema(BaseModel):
    """Representa un producto del catálogo."""
    id: str
    sku: str
    nombre: str
    descripcion: str
    precio: str  # Monto como string para Decimal
    moneda: str
    categoria: str
    activo: bool

    @classmethod
    def from_domain(cls, producto: Producto) -> "ProductoSchema":
        return cls(
            id=str(producto.id),
            sku=str(producto.sku),
            nombre=producto.nombre,
            descripcion=producto.descripcion,
            precio=str(producto.precio.monto),
            moneda=producto.precio.moneda,
            categoria=producto.categoria,
            activo=producto.activo,
        )


class ListaProductosResponse(BaseModel):
    """Respuesta para listar productos."""
    productos: list[ProductoSchema]
    total: int


# =============================================================================
# Schemas para Almacenes
# =============================================================================

class AlmacenSchema(BaseModel):
    """Representa un almacén."""
    id: str
    nombre: str
    ubicacion: str

    @classmethod
    def from_domain(cls, almacen: Almacen) -> "AlmacenSchema":
        return cls(
            id=str(almacen.id),
            nombre=almacen.nombre,
            ubicacion=almacen.ubicacion,
        )


class ListaAlmacenesResponse(BaseModel):
    """Respuesta para listar almacenes."""
    almacenes: list[AlmacenSchema]
    total: int


# =============================================================================
# Schemas para Inventario
# =============================================================================

class ExistenciaSchema(BaseModel):
    """Representa una existencia en inventario."""
    sku: str
    disponible: int


class InventarioAlmacenResponse(BaseModel):
    """Respuesta para consultar inventario de un almacén."""
    almacen_id: str
    nombre: str
    existencias: list[ExistenciaSchema]


# =============================================================================
# Schemas para Pedidos
# =============================================================================

class DireccionRequest(BaseModel):
    """Datos de dirección para el request."""
    calle: str
    numero: str
    colonia: str
    ciudad: str
    codigo_postal: str = Field(..., min_length=5, max_length=5)

    @field_validator("codigo_postal")
    @classmethod
    def validar_cp(cls, v):
        if not v.isdigit():
            raise ValueError("Código postal debe ser numérico")
        return v


class LineaPedidoRequest(BaseModel):
    """Línea de pedido para el request."""
    sku: str
    cantidad: int = Field(..., gt=0)
    precio_unitario: Decimal = Field(..., gt=0)


class PedidoCreado(BaseModel):
    """Request para crear un pedido (checkout)."""
    lineas: list[LineaPedidoRequest]
    direccion: DireccionRequest


class LineaPedidoResponse(BaseModel):
    """Línea de pedido en response."""
    sku: str
    cantidad: int
    precio_unitario: Decimal


class PedidoResponse(BaseModel):
    """Representa un pedido en response."""
    id: str
    cliente_id: str
    estado: str
    total: str
    moneda: str
    direccion_entrega: dict
    lineas: list[LineaPedidoResponse]
    surtidos: list[dict]
    reintentos_pago: int

    @classmethod
    def from_domain(cls, pedido: Pedido) -> "PedidoResponse":
        return cls(
            id=str(pedido.id),
            cliente_id=str(pedido.cliente_id),
            estado=pedido.estado.value,
            total=str(pedido.total.monto),
            moneda=pedido.total.moneda,
            direccion_entrega={
                "calle": pedido.direccion_entrega.calle,
                "numero": pedido.direccion_entrega.numero,
                "colonia": pedido.direccion_entrega.colonia,
                "ciudad": pedido.direccion_entrega.ciudad,
                "codigo_postal": pedido.direccion_entrega.codigo_postal,
            },
            lineas=[
                LineaPedidoResponse(
                    sku=str(l.sku),
                    cantidad=l.cantidad,
                    precio_unitario=l.precio_unitario.monto,
                )
                for l in pedido.lineas
            ],
            surtidos=[
                {
                    "id": str(s.id),
                    "pedido_id": str(s.pedido_id),
                    "almacen_id": str(s.almacen_id),
                    "estado": s.estado.value,
                    "lineas": [{"sku": str(l.sku), "cantidad": l.cantidad} for l in s.lineas],
                }
                for s in pedido.surtidos
            ],
            reintentos_pago=pedido.reintentos_pago,
        )


# =============================================================================
# Schemas para Pago
# =============================================================================

class PagoProcesar(BaseModel):
    """Request para procesar un pago."""
    pedido_id: UUID
    metodo_pago: str = Field(..., description="Método de pago: TARJETA, TRANSFERENCIA, EFECTIVO")
    datos_cliente: Optional[dict] = None


class PagoResponse(BaseModel):
    """Representa un pago en response."""
    id: str
    pedido_id: str
    monto: str
    moneda: str
    metodo_pago: str
    estado: str
    reintentos: int

    @classmethod
    def from_domain(cls, pago: Pago) -> "PagoResponse":
        return cls(
            id=str(pago.id),
            pedido_id=str(pago.pedido_id),
            monto=str(pago.monto.monto),
            moneda=pago.monto.moneda,
            metodo_pago=pago.metodo_pago,
            estado=pago.estado.value,
            reintentos=pago.reintentos,
        )


# =============================================================================
# Schemas para Cancelación
# =============================================================================

class MotivoCancelacion(BaseModel):
    """Request para cancelar un pedido."""
    motivo: str
    autorizado_por_atencion: Optional[bool] = False


# =============================================================================
# Schemas para Despacho/Envío
# =============================================================================

class DespachoDatos(BaseModel):
    """Datos para despachar un pedido."""
    guia: str


class EntregaRegistro(BaseModel):
    """Datos para registrar entrega."""
    exitoso: bool
    observaciones: Optional[str] = None


class EnvioResponse(BaseModel):
    """Representa un envío en response."""
    id: str
    pedido_id: str
    guia: Optional[str]
    estado: str
    intentos: int

    @classmethod
    def from_domain(cls, envio: Envio) -> "EnvioResponse":
        return cls(
            id=str(envio.id),
            pedido_id=str(envio.pedido_id),
            guia=envio.guia.valor if envio.guia else None,
            estado=envio.estado.value,
            intentos=envio.get_intentos_realizados(),
        )


# =============================================================================
# Schemas para Devolución
# =============================================================================

class LineaDevolucionRequest(BaseModel):
    """Línea de devolución para el request."""
    sku: str
    cantidad: int = Field(..., gt=0)


class DevolucionSolicitar(BaseModel):
    """Request para solicitar devolución."""
    pedido_id: UUID
    lineas: list[LineaDevolucionRequest]
    motivo: str
    fecha_entrega: Optional[datetime] = None


class MotivoRechazoDevolucion(BaseModel):
    """Motivo para rechazar una devolución."""
    motivo: str


class DevolucionResponse(BaseModel):
    """Representa una devolución en response."""
    id: str
    pedido_id: str
    estado: str
    motivo: str
    lineas: list[dict]
    fecha_solicitud: datetime

    @classmethod
    def from_domain(cls, devolucion: Devolucion) -> "DevolucionResponse":
        return cls(
            id=str(devolucion.id),
            pedido_id=str(devolucion.pedido_id),
            estado=devolucion.estado.value,
            motivo=devolucion.motivo.valor,
            lineas=[
                {"sku": str(l.sku), "cantidad": l.cantidad}
                for l in devolucion.lineas
            ],
            fecha_solicitud=devolucion.fecha_solicitud,
        )


# =============================================================================
# Schemas para Discrepancia de Inventario
# =============================================================================

class DiscrepanciaInventario(BaseModel):
    """Request para registrar discrepancia de inventario."""
    sku: str
    cantidad_fisica: int


# =============================================================================
# Error Response
# =============================================================================

class ErrorResponse(BaseModel):
    """Formato estándar de respuesta de error."""
    codigo: str
    mensaje: str