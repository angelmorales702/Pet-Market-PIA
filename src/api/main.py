"""FastAPI Application - PetMarket.

API REST que expone los casos de uso del sistema.
Solo llama a los casos de uso de src.application; no contiene reglas de negocio.

Rutas en español y en plural según convención del proyecto.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import FastAPI, Depends, HTTPException, Header, status, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configure logging for error tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.domain.aggregates import (
    Almacen, Cliente, Devolucion, Envio, Pago, Pedido, Producto
)
from src.domain.entities import LineaPedido, LineaDevolucion, Surtido
from src.domain.value_objects import (
    DireccionEntrega, Dinero, Sku, MotivoDevolucion, Guia
)
from src.domain.exceptions import (
    TransicionEstadoInvalidaException,
    CancelacionNoPermitidaError,
    DevolucionNoPermitidaError,
    StockInsuficienteError,
    PedidoNoEncontradoError,
    DevolucionNoEncontradoError,
    AlmacenNoEncontradoError,
    SurtidoNoEncontradoError,
)
from src.application.ports import (
    UnitOfWork, PasarelaPago, ResultadoPago, PublicadorEventos
)
from src.application.use_cases import (
    ConfirmarCheckoutUseCase,
    ProcesarPagoUseCase,
    CancelarPedidoUseCase,
    IniciarYEmpacarSurtidoUseCase,
    DespacharPedidoUseCase,
    RegistrarEntregaUseCase,
    SolicitarDevolucionUseCase,
    AutorizarDevolucionUseCase,
    ProcesarReembolsoUseCase,
    ConsultarEstadoPedidoUseCase,
    ConsultarDiscrepanciaInventarioUseCase,
)
from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
from src.application.in_memory import InMemoryEventPublisher

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

# Usar TEST_DATABASE_URL si está disponible (modo test)
_DB_URL = TEST_DATABASE_URL or DATABASE_URL

engine = create_engine(_DB_URL)
SessionLocal = sessionmaker(bind=engine)


def get_session():
    """Dependency that provides a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_event_publisher():
    """Dependency that provides an event publisher."""
    return InMemoryEventPublisher()


def get_pasarela_pago():
    """Dependency that provides a payment gateway."""
    return FakePasarelaPago()


def get_uow(session=Depends(get_session)):
    """Dependency that provides a Unit of Work."""
    publisher = InMemoryEventPublisher()
    # El session viene por dependencia - si es una session válida, usarla directamente
    # Esto permite que los tests con override funcionen correctamente
    from sqlalchemy.orm import Session
    if isinstance(session, Session):
        # Session ya existe (en tests con override), usarla directamente
        uow = SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)
    else:
        # UoW normal con session factory
        uow = SqlAlchemyUnitOfWork(SessionLocal, publisher)
    return uow


# =============================================================================
# FastAPI App Configuration
# =============================================================================

app = FastAPI(
    title="PetMarket API",
    description="API REST para el sistema de e-commerce de productos de mascotas",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Exception Handlers
# =============================================================================

# Mapeo centralizado de excepciones del dominio a respuestas HTTP
# Formato de respuesta: {"detail": {"codigo": "...", "mensaje": "..."}}
EXCEPTION_HANDLERS = [
    # 409 Conflict - Errores de estado y negocio
    (TransicionEstadoInvalidaException, status.HTTP_409_CONFLICT, "ESTADO_INVALIDO"),
    (CancelacionNoPermitidaError, status.HTTP_409_CONFLICT, "CANCELACION_NO_PERMITIDA"),
    (DevolucionNoPermitidaError, status.HTTP_409_CONFLICT, "DEVOLUCION_NO_PERMITIDA"),
    (StockInsuficienteError, status.HTTP_409_CONFLICT, "STOCK_INSUFICIENTE"),
    # 404 Not Found - Recursos no encontrados
    (PedidoNoEncontradoError, status.HTTP_404_NOT_FOUND, "PEDIDO_NO_ENCONTRADO"),
    (DevolucionNoEncontradoError, status.HTTP_404_NOT_FOUND, "DEVOLUCION_NO_ENCONTRADO"),
    (AlmacenNoEncontradoError, status.HTTP_404_NOT_FOUND, "ALMACEN_NO_ENCONTRADO"),
    (SurtidoNoEncontradoError, status.HTTP_404_NOT_FOUND, "SURTIDO_NO_ENCONTRADO"),
]


def _build_error_detail(codigo: str, mensaje: str) -> dict:
    """Construye el detalle de error en el formato esperado."""
    return {"detail": {"codigo": codigo, "mensaje": mensaje}}


def _get_error_handler(exc: Exception):
    """Obtiene el código HTTP, código de error y mensaje para una excepción."""
    for exc_class, http_code, error_code in EXCEPTION_HANDLERS:
        if isinstance(exc, exc_class):
            # Extraer el identificador relevante según el tipo de excepción
            if hasattr(exc, 'pedido_id'):
                mensaje = f"Pedido {exc.pedido_id} no encontrado"
            elif hasattr(exc, 'devolucion_id'):
                mensaje = f"Devolución {exc.devolucion_id} no encontrada"
            elif hasattr(exc, 'almacen_id'):
                mensaje = f"Almacén {exc.almacen_id} no encontrado"
            elif hasattr(exc, 'surtido_id'):
                mensaje = f"Surtido {exc.surtido_id} no encontrado"
            elif hasattr(exc, 'estado_actual') and hasattr(exc, 'estado_destino'):
                mensaje = f"Transición de estado inválida: {exc.estado_actual} → {exc.estado_destino}"
            elif hasattr(exc, 'estado'):
                # CancelacionNoPermitidaError y DevolucionNoPermitidaError
                mensaje = f"No se puede cancelar un pedido en estado {exc.estado}"
            else:
                mensaje = str(exc)
            return http_code, error_code, mensaje
    return None


@app.exception_handler(TransicionEstadoInvalidaException)
async def handle_transicion_estado(request, exc: TransicionEstadoInvalidaException):
    """Handle TransicionEstadoInvalidaException with 409 Conflict."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(CancelacionNoPermitidaError)
async def handle_cancelacion_no_permitida(request, exc: CancelacionNoPermitidaError):
    """Handle CancelacionNoPermitidaError with 409 Conflict."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(DevolucionNoPermitidaError)
async def handle_devolucion_no_permitida(request, exc: DevolucionNoPermitidaError):
    """Handle DevolucionNoPermitidaError with 409 Conflict."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(StockInsuficienteError)
async def handle_stock_insuficiente(request, exc: StockInsuficienteError):
    """Handle StockInsuficienteError with 409 Conflict."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(PedidoNoEncontradoError)
async def handle_pedido_no_encontrado(request, exc: PedidoNoEncontradoError):
    """Handle PedidoNoEncontradoError with 404 Not Found."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(DevolucionNoEncontradoError)
async def handle_devolucion_no_encontrado(request, exc: DevolucionNoEncontradoError):
    """Handle DevolucionNoEncontradoError with 404 Not Found."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(AlmacenNoEncontradoError)
async def handle_almacen_no_encontrado(request, exc: AlmacenNoEncontradoError):
    """Handle AlmacenNoEncontradoError with 404 Not Found."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(SurtidoNoEncontradoError)
async def handle_surtido_no_encontrado(request, exc: SurtidoNoEncontradoError):
    """Handle SurtidoNoEncontradoError with 404 Not Found."""
    http_code, error_code, mensaje = _get_error_handler(exc)
    return JSONResponse(status_code=http_code, content=_build_error_detail(error_code, mensaje))


@app.exception_handler(ValidationError)
async def handle_validation_error(request, exc: ValidationError):
    """Handle Pydantic validation errors with 422 Unprocessable Entity."""
    # Extraer el primer error de validación
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        loc = ".".join(str(l) for l in first_error.get("loc", []))
        msg = first_error.get("msg", "Error de validación")
        error_type = first_error.get("type", "value_error")

        # Mapear tipos de error a códigos más específicos
        if "sku" in loc.lower() or error_type == "value_error":
            codigo = "SKU_INVALIDO"
        else:
            codigo = "DATOS_INVALIDOS"

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_build_error_detail(codigo, msg)
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_build_error_detail("DATOS_INVALIDOS", "Error de validación")
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request, exc: HTTPException):
    """Handle FastAPI HTTPException with custom error format."""
    if exc.detail and isinstance(exc.detail, dict):
        # Ya está en el formato correcto, envolver en "detail"
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    elif isinstance(exc.detail, str):
        # String simple - convertir a formato estructurado
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content=_build_error_detail("NO_ENCONTRADO", exc.detail))
        elif exc.status_code == 409:
            return JSONResponse(status_code=409, content=_build_error_detail("CONFLICTO", exc.detail))
        else:
            return JSONResponse(status_code=exc.status_code, content=_build_error_detail("ERROR", exc.detail))
    else:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Translate unexpected exceptions to HTTP 500 error responses."""
    # Log del error completo para diagnóstico
    logger.exception("Error interno del servidor en %s %s: %s", request.method, request.url.path, str(exc))
    # Nunca devolver 500 con información sensible
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_build_error_detail("ERROR_INTERNO", "Error interno del servidor")
    )


# =============================================================================
# Schemas (inline to avoid circular imports)
# =============================================================================

class DireccionRequest(BaseModel):
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
    """Request for a line item in a pedido.

    El precio_unitario NO se acepta del cliente: proviene del catálogo de productos.
    """
    model_config = {"extra": "forbid"}  # Rechaza campos inesperados como precio_unitario del cliente

    sku: str
    cantidad: int = Field(..., gt=0, description="Cantidad de unidades a pedir")


class PedidoCreado(BaseModel):
    """Request body para crear un pedido.

    - lineas: requiere al menos 1 elemento (validación Pydantic)
    - precio_unitario en cada línea es RECHAZADO (se busca en el catálogo)
    """
    lineas: list[LineaPedidoRequest] = Field(..., min_length=1, description="Al menos una línea requerida")
    direccion: DireccionRequest


class ProductoSchema(BaseModel):
    id: str
    sku: str
    nombre: str
    descripcion: str
    precio: str
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
    productos: list[ProductoSchema]
    total: int


class AlmacenSchema(BaseModel):
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
    almacenes: list[AlmacenSchema]
    total: int


class ExistenciaSchema(BaseModel):
    sku: str
    disponible: int


class InventarioAlmacenResponse(BaseModel):
    almacen_id: str
    nombre: str
    existencias: list[ExistenciaSchema]


class LineaPedidoResponse(BaseModel):
    sku: str
    cantidad: int
    precio_unitario: Decimal


class PedidoResponse(BaseModel):
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


class LineaProdRequest(BaseModel):
    sku: str
    cantidad: int = Field(..., gt=0)
    precio_unitario: Decimal = Field(..., gt=0)


class PagoProcesar(BaseModel):
    pedido_id: UUID
    metodo_pago: str = Field(..., description="Método de pago: TARJETA, TRANSFERENCIA, EFECTIVO")
    datos_cliente: Optional[dict] = None


class PagoResponse(BaseModel):
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


class MotivoCancelacion(BaseModel):
    motivo: str
    autorizado_por_atencion: Optional[bool] = False


class DespachoDatos(BaseModel):
    guia: str


class EntregaRegistro(BaseModel):
    exitoso: bool
    observaciones: Optional[str] = None


class EnvioResponse(BaseModel):
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


class LineaDevolucionRequest(BaseModel):
    sku: str
    cantidad: int = Field(..., gt=0)


class DevolucionSolicitar(BaseModel):
    pedido_id: UUID
    lineas: list[LineaDevolucionRequest]
    motivo: str
    fecha_entrega: Optional[datetime] = None


class MotivoRechazoDevolucion(BaseModel):
    motivo: str


class DevolucionResponse(BaseModel):
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


class DiscrepanciaInventario(BaseModel):
    sku: str
    cantidad_fisica: int


# =============================================================================
# Pasarela de Pago Fake (desarrollo)
# =============================================================================

class FakePasarelaPago(PasarelaPago):
    """Pasarela de pago fake para desarrollo y tests."""

    def cobrar(self, monto: Dinero, metodo_pago: str, datos_cliente: dict) -> ResultadoPago:
        trans_id = f"txn_{monto.monto}_{int(datetime.now().timestamp() * 1000) % 1000000}"
        return ResultadoPago(aprobado=True, transaccion_id=trans_id)

    def reembolsar(self, transaccion_id: str, monto: Dinero) -> ResultadoPago:
        return ResultadoPago(aprobado=True, transaccion_id=transaccion_id)


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment and orchestration."""
    return {"status": "healthy", "service": "petmarket-api"}


# --- Productos (Catálogo) - US-001 ---

@app.get("/productos", response_model=ListaProductosResponse)
async def listar_productos(
    activos: bool = True,
    categoria: str | None = None,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
):
    """US-001: Listar productos del catálogo."""
    with uow:
        productos = uow.productos.obtener_activos() if activos else uow.productos.obtener_todos()
        if categoria:
            productos = [p for p in productos if p.categoria == categoria]
        return ListaProductosResponse(
            productos=[ProductoSchema.from_domain(p) for p in productos],
            total=len(productos),
        )


@app.get("/productos/{sku}")
async def obtener_producto(
    sku: str,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
):
    """US-001: Obtener detalles de un producto por SKU."""
    with uow:
        try:
            producto = uow.productos.obtener_por_sku(Sku.of(sku))
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "codigo": "SKU_INVALIDO",
                    "mensaje": f"Formato de SKU inválido: {sku}. El formato debe ser SKU-XXXXX (5 dígitos)"
                }
            )
        if not producto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"codigo": "PRODUCTO_NO_ENCONTRADO", "mensaje": f"Producto con SKU {sku} no encontrado"},
            )
        return ProductoSchema.from_domain(producto)


# --- Almacenes e Inventario ---

@app.get("/almacenes")
async def listar_almacenes(uow: SqlAlchemyUnitOfWork = Depends(get_uow)):
    """Listar almacenes disponibles."""
    with uow:
        almacenes = uow.almacenes.obtener_todos()
        return ListaAlmacenesResponse(
            almacenes=[AlmacenSchema.from_domain(a) for a in almacenes],
            total=len(almacenes),
        )


@app.get("/almacenes/{almacen_id}/inventario")
async def obtener_inventario_almacen(
    almacen_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
):
    """US-001: Consultar inventario de un almacén."""
    with uow:
        almacen = uow.almacenes.obtener_por_id(almacen_id)
        if not almacen:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"codigo": "ALMACEN_NO_ENCONTRADO", "mensaje": f"Almacén {almacen_id} no encontrado"},
            )
        return InventarioAlmacenResponse(
            almacen_id=str(almacen_id),
            nombre=almacen.nombre,
            existencias=[
                ExistenciaSchema(sku=sku, disponible=existencia.cantidad_disponible)
                for sku, existencia in almacen.existencias.items()
            ],
        )


# --- Checkout - Crear Pedido - US-004 ---
# NOTA: El precio_unitario NO se acepta del cliente. Se busca en el catálogo.

@app.post("/pedidos", response_model=PedidoResponse, status_code=status.HTTP_201_CREATED)
async def crear_pedido(
    pedido_data: PedidoCreado = Body(...),
    cliente_id: str = Header(..., alias="X-Cliente-Id"),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-004: Confirmar checkout y crear pedido.

    El precio se obtiene del catálogo (producto por SKU), NO del cliente.
    El total del pedido = sum(precio_producto * cantidad_cada_linea).
    """
    with uow:
        lineas = []
        for item in pedido_data.lineas:
            # Validar SKU y obtener producto del catálogo
            try:
                sku_vo = Sku.of(item.sku)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"codigo": "SKU_INVALIDO", "mensaje": str(e)}
                )

            # Obtener producto del catálogo para obtener el precio
            producto = uow.productos.obtener_por_sku(sku_vo)
            if not producto:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "codigo": "PRODUCTO_NO_ENCONTRADO",
                        "mensaje": f"Producto con SKU {item.sku} no encontrado en el catálogo"
                    }
                )

            # Verificar que el SKU sea activo
            if not producto.activo:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "codigo": "PRODUCTO_INACTIVO",
                        "mensaje": f"Producto con SKU {item.sku} está inactivo"
                    }
                )

            # Crear línea con PRECIO DEL CATÁLOGO (no del cliente)
            lineas.append(
                LineaPedido(
                    sku=sku_vo,
                    cantidad=item.cantidad,
                    precio_unitario=producto.precio,
                )
            )

        direccion = DireccionEntrega(
            calle=pedido_data.direccion.calle,
            numero=pedido_data.direccion.numero,
            colonia=pedido_data.direccion.colonia,
            ciudad=pedido_data.direccion.ciudad,
            codigo_postal=pedido_data.direccion.codigo_postal,
        )

        use_case = ConfirmarCheckoutUseCase(uow, publisher)
        pedido = use_case.ejecutar(
            cliente_id=UUID(cliente_id),
            lineas=lineas,
            direccion=direccion,
        )

        return PedidoResponse.from_domain(pedido)


# --- Pago - Procesar - US-003, US-004 ---

@app.post("/pagos", response_model=PagoResponse)
async def procesar_pago(
    pago_data: PagoProcesar = Body(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
):
    """US-003, US-004: Procesar pago de un pedido."""
    with uow:
        publisher = InMemoryEventPublisher()
        pasarela = FakePasarelaPago()
        use_case = ProcesarPagoUseCase(uow, publisher, pasarela)

        pago = use_case.ejecutar(
            pedido_id=pago_data.pedido_id,
            metodo_pago=pago_data.metodo_pago,
            datos_cliente=pago_data.datos_cliente or {},
        )

        return PagoResponse.from_domain(pago)


# --- Cancelar Pedido - US-008, US-009 ---

@app.post("/pedidos/{pedido_id}/cancelar")
async def cancelar_pedido(
    pedido_id: UUID,
    motivo: MotivoCancelacion = Body(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-008, US-009: Cancelar un pedido."""
    with uow:
        use_case = CancelarPedidoUseCase(uow, publisher)
        pedido = use_case.ejecutar(
            pedido_id=pedido_id,
            motivo=motivo.motivo,
            autorizado_por_atencion=motivo.autorizado_por_atencion or False,
        )
        return PedidoResponse.from_domain(pedido)


# --- Preparar y Empacar - US-007 ---

@app.post("/pedidos/{pedido_id}/iniciar-preparacion")
async def iniciar_preparacion(
    pedido_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-007: Iniciar preparación de un pedido."""
    with uow:
        use_case = IniciarYEmpacarSurtidoUseCase(uow, publisher)
        pedido = use_case.iniciar_preparacion(pedido_id)
        return PedidoResponse.from_domain(pedido)


@app.post("/pedidos/{pedido_id}/confirmar-empaque")
async def confirmar_empaque(
    pedido_id: UUID,
    almacen_id: UUID = Body(..., embed=True),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-007: Confirmar empaquetado de un surtido."""
    with uow:
        use_case = IniciarYEmpacarSurtidoUseCase(uow, publisher)
        pedido = use_case.confirmar_empaque_surtido(pedido_id, almacen_id)
        return PedidoResponse.from_domain(pedido)


# --- Enviar - US-006 ---

@app.post("/pedidos/{pedido_id}/enviar")
async def despachar_pedido(
    pedido_id: UUID,
    datos: DespachoDatos = Body(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-006: Despachar el pedido generando el Envío y la Guía."""
    with uow:
        use_case = DespacharPedidoUseCase(uow, publisher)
        envio = use_case.ejecutar(pedido_id, datos.guia)
        return EnvioResponse.from_domain(envio)


# --- Entrega - US-010, US-011 ---

@app.post("/pedidos/{pedido_id}/entrega")
async def registrar_entrega(
    pedido_id: UUID,
    datos: EntregaRegistro = Body(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-010, US-011: Registrar intento de entrega."""
    with uow:
        use_case = RegistrarEntregaUseCase(uow, publisher)
        envio = use_case.ejecutar(
            pedido_id=pedido_id,
            exitoso=datos.exitoso,
            observaciones=datos.observaciones or "",
        )
        return EnvioResponse.from_domain(envio)


# --- Consultar Pedido - US-012 ---

@app.get("/pedidos/{pedido_id}")
async def consultar_pedido(
    pedido_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
):
    """Consultar el estado de un pedido y sus surtidos/envíos."""
    with uow:
        datos = uow.pedidos.obtener_por_id(pedido_id)
        if not datos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"codigo": "PEDIDO_NO_ENCONTRADO", "mensaje": f"Pedido {pedido_id} no encontrado"},
            )

        estado = ConsultarEstadoPedidoUseCase(uow)
        return estado.ejecutar(pedido_id)


@app.get("/clientes/{cliente_id}/pedidos")
async def listar_pedidos_cliente(
    cliente_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
):
    """US-012: Listar pedidos de un cliente con estado de surtidos."""
    with uow:
        pedidos = uow.pedidos.obtener_por_cliente(cliente_id)
        resultados = []
        for pedido in pedidos:
            item = {
                "pedido_id": str(pedido.id),
                "estado": pedido.estado.value,
                "total": str(pedido.total.monto),
                "moneda": pedido.total.moneda,
                "surtidos": [
                    {
                        "surtido_id": str(s.id),
                        "almacen_id": str(s.almacen_id),
                        "estado": s.estado.value,
                        "lineas": [{"sku": str(l.sku), "cantidad": l.cantidad} for l in s.lineas],
                    }
                    for s in pedido.surtidos
                ],
            }
            resultados.append(item)
        return {"pedidos": resultados, "total": len(resultados)}


# --- Devolución - US-013, US-014, US-015 ---

@app.post("/devoluciones")
async def solicitar_devolucion(
    devolucion_data: DevolucionSolicitar = Body(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-013, US-014: Solicitar una devolución."""
    with uow:
        lineas = [
            LineaDevolucion(
                sku=Sku.of(item.sku),
                cantidad=item.cantidad,
            )
            for item in devolucion_data.lineas
        ]

        use_case = SolicitarDevolucionUseCase(uow, publisher)
        devolucion = use_case.ejecutar(
            pedido_id=devolucion_data.pedido_id,
            lineas=lineas,
            motivo=MotivoDevolucion.of(devolucion_data.motivo),
            fecha_entrega=devolucion_data.fecha_entrega or datetime.now(),
        )
        return DevolucionResponse.from_domain(devolucion)


@app.post("/devoluciones/{devolucion_id}/autorizar")
async def autorizar_devolucion(
    devolucion_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-014: Autorizar una devolución."""
    with uow:
        use_case = AutorizarDevolucionUseCase(uow, publisher)
        devolucion = use_case.autorizar(devolucion_id)
        return DevolucionResponse.from_domain(devolucion)


@app.post("/devoluciones/{devolucion_id}/rechazar")
async def rechazar_devolucion(
    devolucion_id: UUID,
    motivo: MotivoRechazoDevolucion = Body(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """Rechazar una devolución."""
    with uow:
        use_case = AutorizarDevolucionUseCase(uow, publisher)
        devolucion = use_case.rechazar(devolucion_id, motivo.motivo)
        return DevolucionResponse.from_domain(devolucion)


@app.post("/devoluciones/{devolucion_id}/confirmar-recepcion")
async def confirmar_recepcion(
    devolucion_id: UUID,
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
    pasarela: PasarelaPago = Depends(get_pasarela_pago),
):
    """US-014: Confirmar recepción en almacén."""
    with uow:
        use_case = ProcesarReembolsoUseCase(uow, publisher, pasarela)
        devolucion = use_case.confirmar_recepcion_y_reembolsar(devolucion_id)
        return DevolucionResponse.from_domain(devolucion)


# --- Detectar Discrepancia de Inventario - US-016 ---

@app.post("/almacenes/{almacen_id}/discrepancia")
async def detectar_discrepancia(
    almacen_id: UUID,
    datos: DiscrepanciaInventario = Body(...),
    uow: SqlAlchemyUnitOfWork = Depends(get_uow),
    publisher: PublicadorEventos = Depends(get_event_publisher),
):
    """US-016: Detectar discrepancia entre inventario web y físico."""
    with uow:
        use_case = ConsultarDiscrepanciaInventarioUseCase(uow, publisher)
        use_case.ejecutar(almacen_id, Sku.of(datos.sku), datos.cantidad_fisica)
        return {"status": "discrepancia_registrada", "almacen_id": str(almacen_id)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)