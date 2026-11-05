"""Implementaciones concretas de Repositorios usando SQLAlchemy 2.0.

Estos repositorios implementan los puertos definidos en src/application/ports.py
y traducen entre modelos de persistencia y agregados del dominio.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from src.application.ports import (
    RepositorioAlmacen,
    RepositorioCliente,
    RepositorioDevolucion,
    RepositorioEnvio,
    RepositorioPago,
    RepositorioPedido,
    RepositorioProducto,
    RepositorioSurtido,
)
from src.domain.aggregates import Almacen, Cliente, Devolucion, Envio, Pago, Pedido, Producto
from src.domain.entities import (
    ExistenciaProducto,
    IntentoEntrega,
    LineaDevolucion,
    LineaPedido,
    Surtido,
)
from src.domain.value_objects import (
    DireccionEntrega,
    Dinero,
    EstadoDevolucion,
    EstadoEnvio,
    EstadoPago,
    EstadoSurtido,
    Guia,
    MotivoDevolucion,
    Sku,
)
from src.domain.state_machine import EstadoPedido
from .models import (
    AlmacenModel,
    ClienteModel,
    DevolucionModel,
    DireccionModel,
    EnvioModel,
    ExistenciaModel,
    IntentoEntregaModel,
    LineaDevolucionModel,
    LineaPedidoModel,
    LineaSurtidoModel,
    PagoModel,
    PedidoModel,
    ProductoModel,
    SurtidoModel,
)


# =============================================================================
# MAPPERS: Persistencia <-> Dominio
# =============================================================================

def _map_direccion_to_domain(model: DireccionModel) -> DireccionEntrega:
    return DireccionEntrega(
        calle=model.calle,
        numero=model.numero,
        colonia=model.colonia,
        ciudad=model.ciudad,
        codigo_postal=model.codigo_postal,
    )


def _map_direccion_from_domain(direccion: DireccionEntrega, cliente_id: UUID, id: Optional[UUID] = None) -> DireccionModel:
    from uuid import uuid4
    return DireccionModel(
        id=id or uuid4(),
        cliente_id=cliente_id,
        calle=direccion.calle,
        numero=direccion.numero,
        colonia=direccion.colonia,
        ciudad=direccion.ciudad,
        codigo_postal=direccion.codigo_postal,
    )


def _map_cliente_to_domain(model: ClienteModel) -> Cliente:
    direcciones = [_map_direccion_to_domain(d) for d in model.direcciones]
    return Cliente(
        id=model.id,
        nombre=model.nombre,
        email=model.email,
        telefono=model.telefono,
        direcciones=direcciones,
    )


def _map_cliente_from_domain(cliente: Cliente) -> ClienteModel:
    from uuid import uuid4
    model = ClienteModel(
        id=cliente.id,
        nombre=cliente.nombre,
        email=cliente.email,
        telefono=cliente.telefono,
    )
    # Las direcciones se manejan por separado
    return model


def _map_producto_to_domain(model: ProductoModel) -> Producto:
    return Producto(
        id=model.id,
        sku=Sku.of(model.sku),
        nombre=model.nombre,
        descripcion=model.descripcion,
        precio=Dinero(model.precio_monto, model.precio_moneda),
        categoria=model.categoria,
        activo=model.activo,
    )


def _map_producto_from_domain(producto: Producto) -> ProductoModel:
    from uuid import uuid4
    return ProductoModel(
        id=producto.id,
        sku=str(producto.sku),
        nombre=producto.nombre,
        descripcion=producto.descripcion,
        precio_monto=producto.precio.monto,
        precio_moneda=producto.precio.moneda,
        categoria=producto.categoria,
        activo=producto.activo,
    )


def _map_existencia_to_domain(model: ExistenciaModel) -> ExistenciaProducto:
    return ExistenciaProducto(
        producto_id=model.producto_id,
        almacen_id=model.almacen_id,
        sku=Sku.of(model.sku),
        cantidad_disponible=model.cantidad_disponible,
        cantidad_reservada=model.cantidad_reservada,
    )


def _map_existencia_from_domain(existencia: ExistenciaProducto) -> ExistenciaModel:
    from uuid import uuid4
    return ExistenciaModel(
        id=uuid4(),
        almacen_id=existencia.almacen_id,
        producto_id=existencia.producto_id,
        sku=str(existencia.sku),
        cantidad_disponible=existencia.cantidad_disponible,
        cantidad_reservada=existencia.cantidad_reservada,
    )


def _map_almacen_to_domain(model: AlmacenModel) -> Almacen:
    existencias = [_map_existencia_to_domain(e) for e in model.existencias]
    almacen = Almacen(
        id=model.id,
        nombre=model.nombre,
        ubicacion=model.ubicacion,
    )
    # Agregar existencias al almacén
    for ex in existencias:
        almacen.existencias[str(ex.sku)] = ex
    return almacen


def _map_almacen_from_domain(almacen: Almacen) -> AlmacenModel:
    from uuid import uuid4
    model = AlmacenModel(
        id=almacen.id,
        nombre=almacen.nombre,
        ubicacion=almacen.ubicacion,
    )
    # Las existencias se manejan por separado
    return model


def _map_linea_pedido_to_domain(model: LineaPedidoModel) -> LineaPedido:
    return LineaPedido(
        sku=Sku.of(model.sku),
        cantidad=model.cantidad,
        precio_unitario=Dinero(model.precio_unitario_monto, model.precio_unitario_moneda),
    )


def _map_linea_pedido_from_domain(linea: LineaPedido, pedido_id: UUID, id: Optional[UUID] = None) -> LineaPedidoModel:
    from uuid import uuid4
    return LineaPedidoModel(
        id=id or uuid4(),
        pedido_id=pedido_id,
        sku=str(linea.sku),
        cantidad=linea.cantidad,
        precio_unitario_monto=linea.precio_unitario.monto,
        precio_unitario_moneda=linea.precio_unitario.moneda,
    )


def _map_surtido_to_domain(model: SurtidoModel) -> Surtido:
    lineas = [_map_linea_pedido_to_domain(l) for l in model.lineas]
    return Surtido(
        id=model.id,
        pedido_id=model.pedido_id,
        almacen_id=model.almacen_id,
        lineas=lineas,
        estado=EstadoSurtido(model.estado),
    )


def _map_surtido_from_domain(surtido: Surtido) -> SurtidoModel:
    from uuid import uuid4
    return SurtidoModel(
        id=surtido.id,
        pedido_id=surtido.pedido_id,
        almacen_id=surtido.almacen_id,
        estado=surtido.estado.value,
    )


def _map_pedido_to_domain(model: PedidoModel) -> Pedido:
    lineas = [_map_linea_pedido_to_domain(l) for l in model.lineas]
    direccion = DireccionEntrega(
        calle=model.direccion_calle,
        numero=model.direccion_numero,
        colonia=model.direccion_colonia,
        ciudad=model.direccion_ciudad,
        codigo_postal=model.direccion_codigo_postal,
    )
    pedido = Pedido(
        id=model.id,
        cliente_id=model.cliente_id,
        lineas=lineas,
        direccion_entrega=direccion,
        estado=EstadoPedido(model.estado),
        reintentos_pago=model.reintentos_pago,
        fecha_creacion=model.fecha_creacion,
        fecha_actualizacion=model.fecha_actualizacion,
    )
    # Surtidos se cargan por separado si se necesitan
    if model.surtidos:
        pedido.surtidos = [_map_surtido_to_domain(s) for s in model.surtidos]
    return pedido


def _map_pedido_from_domain(pedido: Pedido) -> PedidoModel:
    from uuid import uuid4
    return PedidoModel(
        id=pedido.id,
        cliente_id=pedido.cliente_id,
        estado=pedido.estado.value,
        direccion_calle=pedido.direccion_entrega.calle,
        direccion_numero=pedido.direccion_entrega.numero,
        direccion_colonia=pedido.direccion_entrega.colonia,
        direccion_ciudad=pedido.direccion_entrega.ciudad,
        direccion_codigo_postal=pedido.direccion_entrega.codigo_postal,
        reintentos_pago=pedido.reintentos_pago,
        fecha_creacion=pedido.fecha_creacion,
        fecha_actualizacion=pedido.fecha_actualizacion,
    )


def _map_pago_to_domain(model: PagoModel) -> Pago:
    return Pago(
        id=model.id,
        pedido_id=model.pedido_id,
        monto=Dinero(model.monto, model.moneda),
        metodo_pago=model.metodo_pago,
        estado=EstadoPago(model.estado),
        reintentos=model.reintentos,
        motivo_rechazo=model.motivo_rechazo,
        fecha_creacion=model.fecha_creacion,
        fecha_actualizacion=model.fecha_actualizacion,
    )


def _map_pago_from_domain(pago: Pago) -> PagoModel:
    from uuid import uuid4
    return PagoModel(
        id=pago.id,
        pedido_id=pago.pedido_id,
        monto=pago.monto.monto,
        moneda=pago.monto.moneda,
        metodo_pago=pago.metodo_pago,
        estado=pago.estado.value,
        reintentos=pago.reintentos,
        motivo_rechazo=pago.motivo_rechazo,
        fecha_creacion=pago.fecha_creacion,
        fecha_actualizacion=pago.fecha_actualizacion,
    )


def _map_intento_to_domain(model: IntentoEntregaModel) -> IntentoEntrega:
    return IntentoEntrega(
        id=model.id,
        envio_id=model.envio_id,
        exitoso=model.exitoso,
        numero_intento=model.numero_intento,
        observaciones=model.observaciones or "",
    )


def _map_intento_from_domain(intento: IntentoEntrega, envio_id: UUID, id: Optional[UUID] = None) -> IntentoEntregaModel:
    from uuid import uuid4
    return IntentoEntregaModel(
        id=id or uuid4(),
        envio_id=envio_id,
        exitoso=intento.exitoso,
        numero_intento=intento.numero_intento,
        observaciones=intento.observaciones,
    )


def _map_envio_to_domain(model: EnvioModel) -> Envio:
    intentos = [_map_intento_to_domain(i) for i in model.intentos]
    envio = Envio(
        id=model.id,
        pedido_id=model.pedido_id,
        guia=Guia.of(model.guia) if model.guia else None,
        estado=EstadoEnvio(model.estado),
        intentos=intentos,
        fecha_creacion=model.fecha_creacion,
        fecha_actualizacion=model.fecha_actualizacion,
    )
    return envio


def _map_envio_from_domain(envio: Envio) -> EnvioModel:
    from uuid import uuid4
    return EnvioModel(
        id=envio.id,
        pedido_id=envio.pedido_id,
        guia=envio.guia.valor if envio.guia else None,
        estado=envio.estado.value,
        fecha_creacion=envio.fecha_creacion,
        fecha_actualizacion=envio.fecha_actualizacion,
    )


def _map_linea_devolucion_to_domain(model: LineaDevolucionModel) -> LineaDevolucion:
    return LineaDevolucion(
        sku=Sku.of(model.sku),
        cantidad=model.cantidad,
    )


def _map_linea_devolucion_from_domain(linea: LineaDevolucion, devolucion_id: UUID, id: Optional[UUID] = None) -> LineaDevolucionModel:
    from uuid import uuid4
    return LineaDevolucionModel(
        id=id or uuid4(),
        devolucion_id=devolucion_id,
        sku=str(linea.sku),
        cantidad=linea.cantidad,
    )


def _map_devolucion_to_domain(model: DevolucionModel) -> Devolucion:
    lineas = [_map_linea_devolucion_to_domain(l) for l in model.lineas]
    return Devolucion(
        id=model.id,
        pedido_id=model.pedido_id,
        lineas=lineas,
        motivo=MotivoDevolucion.of(model.motivo),
        estado=EstadoDevolucion(model.estado),
        fecha_solicitud=model.fecha_solicitud,
        fecha_autorizacion=model.fecha_autorizacion,
        fecha_recepcion_almacen=model.fecha_recepcion_almacen,
        fecha_reembolso=model.fecha_reembolso,
    )


def _map_devolucion_from_domain(devolucion: Devolucion) -> DevolucionModel:
    from uuid import uuid4
    return DevolucionModel(
        id=devolucion.id,
        pedido_id=devolucion.pedido_id,
        motivo=devolucion.motivo.valor,
        estado=devolucion.estado.value,
        fecha_solicitud=devolucion.fecha_solicitud,
        fecha_autorizacion=devolucion.fecha_autorizacion,
        fecha_recepcion_almacen=devolucion.fecha_recepcion_almacen,
        fecha_reembolso=devolucion.fecha_reembolso,
        motivo_rechazo=None,  # Se maneja por separado si hace falta
    )


# =============================================================================
# REPOSITORIOS
# =============================================================================

class SqlAlchemyRepositorioCliente(RepositorioCliente):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, cliente: Cliente) -> None:
        model = _map_cliente_from_domain(cliente)
        self._session.merge(model)
        # Guardar direcciones
        for direccion in cliente.direcciones:
            dir_model = _map_direccion_from_domain(direccion, cliente.id)
            self._session.merge(dir_model)

    def obtener_por_id(self, cliente_id: UUID) -> Optional[Cliente]:
        model = self._session.get(ClienteModel, cliente_id, options=[selectinload(ClienteModel.direcciones)])
        return _map_cliente_to_domain(model) if model else None

    def obtener_por_email(self, email: str) -> Optional[Cliente]:
        stmt = select(ClienteModel).where(ClienteModel.email == email).options(selectinload(ClienteModel.direcciones))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_cliente_to_domain(model) if model else None


class SqlAlchemyRepositorioProducto(RepositorioProducto):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, producto: Producto) -> None:
        model = _map_producto_from_domain(producto)
        self._session.merge(model)

    def obtener_por_id(self, producto_id: UUID) -> Optional[Producto]:
        model = self._session.get(ProductoModel, producto_id)
        return _map_producto_to_domain(model) if model else None

    def obtener_por_sku(self, sku: Sku) -> Optional[Producto]:
        stmt = select(ProductoModel).where(ProductoModel.sku == str(sku))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_producto_to_domain(model) if model else None

    def obtener_activos(self) -> List[Producto]:
        stmt = select(ProductoModel).where(ProductoModel.activo == True)
        models = self._session.execute(stmt).scalars().all()
        return [_map_producto_to_domain(m) for m in models]

    def obtener_todos(self) -> List[Producto]:
        stmt = select(ProductoModel)
        models = self._session.execute(stmt).scalars().all()
        return [_map_producto_to_domain(m) for m in models]


class SqlAlchemyRepositorioAlmacen(RepositorioAlmacen):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, almacen: Almacen) -> None:
        model = _map_almacen_from_domain(almacen)
        self._session.merge(model)
        # Guardar existencias - buscar por (almacen_id, sku) y actualizar o crear
        from sqlalchemy import select, or_
        for ex in almacen.existencias.values():
            stmt = select(ExistenciaModel).where(
                ExistenciaModel.almacen_id == almacen.id,
                ExistenciaModel.sku == str(ex.sku)
            )
            ex_model = self._session.execute(stmt).scalar_one_or_none()
            if ex_model:
                # Actualizar los campos
                ex_model.producto_id = ex.producto_id
                ex_model.cantidad_disponible = ex.cantidad_disponible
                ex_model.cantidad_reservada = ex.cantidad_reservada
            else:
                # Crear nueva existencia
                from uuid import uuid4
                new_ex = ExistenciaModel(
                    id=uuid4(),
                    almacen_id=almacen.id,
                    producto_id=ex.producto_id,
                    sku=str(ex.sku),
                    cantidad_disponible=ex.cantidad_disponible,
                    cantidad_reservada=ex.cantidad_reservada,
                )
                self._session.add(new_ex)

    def obtener_por_id(self, almacen_id: UUID) -> Optional[Almacen]:
        stmt = select(AlmacenModel).where(AlmacenModel.id == almacen_id).options(selectinload(AlmacenModel.existencias))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_almacen_to_domain(model) if model else None

    def obtener_todos(self) -> List[Almacen]:
        stmt = select(AlmacenModel).options(selectinload(AlmacenModel.existencias))
        models = self._session.execute(stmt).scalars().all()
        return [_map_almacen_to_domain(m) for m in models]


class SqlAlchemyRepositorioPedido(RepositorioPedido):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, pedido: Pedido) -> None:
        model = _map_pedido_from_domain(pedido)
        self._session.merge(model)
        # Guardar líneas
        for linea in pedido.lineas:
            linea_model = _map_linea_pedido_from_domain(linea, pedido.id)
            self._session.merge(linea_model)
        # Guardar surtidos
        for surtido in pedido.surtidos:
            surtido_model = _map_surtido_from_domain(surtido)
            self._session.merge(surtido_model)
            for linea in surtido.lineas:
                linea_surtido_model = LineaSurtidoModel(
                    id=linea.__dict__.get('_id') or uuid4(),
                    surtido_id=surtido.id,
                    sku=str(linea.sku),
                    cantidad=linea.cantidad,
                    precio_unitario_monto=linea.precio_unitario.monto,
                    precio_unitario_moneda=linea.precio_unitario.moneda,
                )
                self._session.merge(linea_surtido_model)

    def obtener_por_id(self, pedido_id: UUID) -> Optional[Pedido]:
        stmt = select(PedidoModel).where(PedidoModel.id == pedido_id).options(
            selectinload(PedidoModel.lineas),
            selectinload(PedidoModel.surtidos).selectinload(SurtidoModel.lineas),
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_pedido_to_domain(model) if model else None

    def obtener_por_cliente(self, cliente_id: UUID) -> List[Pedido]:
        stmt = select(PedidoModel).where(PedidoModel.cliente_id == cliente_id).options(selectinload(PedidoModel.lineas))
        models = self._session.execute(stmt).scalars().all()
        return [_map_pedido_to_domain(m) for m in models]

    def obtener_por_estado(self, estado: str) -> List[Pedido]:
        stmt = select(PedidoModel).where(PedidoModel.estado == estado).options(selectinload(PedidoModel.lineas))
        models = self._session.execute(stmt).scalars().all()
        return [_map_pedido_to_domain(m) for m in models]


class SqlAlchemyRepositorioPago(RepositorioPago):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, pago: Pago) -> None:
        model = _map_pago_from_domain(pago)
        self._session.merge(model)

    def obtener_por_id(self, pago_id: UUID) -> Optional[Pago]:
        model = self._session.get(PagoModel, pago_id)
        return _map_pago_to_domain(model) if model else None

    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Pago]:
        stmt = select(PagoModel).where(PagoModel.pedido_id == pedido_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_pago_to_domain(model) if model else None


class SqlAlchemyRepositorioEnvio(RepositorioEnvio):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, envio: Envio) -> None:
        model = _map_envio_from_domain(envio)
        self._session.merge(model)
        # Guardar intentos
        for intento in envio.intentos:
            intento_model = _map_intento_from_domain(intento, envio.id)
            self._session.merge(intento_model)

    def obtener_por_id(self, envio_id: UUID) -> Optional[Envio]:
        stmt = select(EnvioModel).where(EnvioModel.id == envio_id).options(selectinload(EnvioModel.intentos))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_envio_to_domain(model) if model else None

    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Envio]:
        stmt = select(EnvioModel).where(EnvioModel.pedido_id == pedido_id).options(selectinload(EnvioModel.intentos))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_envio_to_domain(model) if model else None

    def obtener_por_guia(self, guia: Guia) -> Optional[Envio]:
        stmt = select(EnvioModel).where(EnvioModel.guia == guia.valor).options(selectinload(EnvioModel.intentos))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_envio_to_domain(model) if model else None


class SqlAlchemyRepositorioDevolucion(RepositorioDevolucion):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, devolucion: Devolucion) -> None:
        model = _map_devolucion_from_domain(devolucion)
        self._session.merge(model)
        # Guardar líneas
        for linea in devolucion.lineas:
            linea_model = _map_linea_devolucion_from_domain(linea, devolucion.id)
            self._session.merge(linea_model)

    def obtener_por_id(self, devolucion_id: UUID) -> Optional[Devolucion]:
        stmt = select(DevolucionModel).where(DevolucionModel.id == devolucion_id).options(selectinload(DevolucionModel.lineas))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_devolucion_to_domain(model) if model else None

    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Devolucion]:
        stmt = select(DevolucionModel).where(DevolucionModel.pedido_id == pedido_id).options(selectinload(DevolucionModel.lineas))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_devolucion_to_domain(model) if model else None


class SqlAlchemyRepositorioSurtido(RepositorioSurtido):
    def __init__(self, session: Session):
        self._session = session

    def guardar(self, surtido: Surtido) -> None:
        model = _map_surtido_from_domain(surtido)
        self._session.merge(model)
        for linea in surtido.lineas:
            linea_model = LineaSurtidoModel(
                id=linea.__dict__.get('_id') or uuid4(),
                surtido_id=surtido.id,
                sku=str(linea.sku),
                cantidad=linea.cantidad,
                precio_unitario_monto=linea.precio_unitario.monto,
                precio_unitario_moneda=linea.precio_unitario.moneda,
            )
            self._session.merge(linea_model)

    def obtener_por_id(self, surtido_id: UUID) -> Optional[Surtido]:
        stmt = select(SurtidoModel).where(SurtidoModel.id == surtido_id).options(selectinload(SurtidoModel.lineas))
        model = self._session.execute(stmt).scalar_one_or_none()
        return _map_surtido_to_domain(model) if model else None

    def obtener_por_pedido(self, pedido_id: UUID) -> List[Surtido]:
        stmt = select(SurtidoModel).where(SurtidoModel.pedido_id == pedido_id).options(selectinload(SurtidoModel.lineas))
        models = self._session.execute(stmt).scalars().all()
        return [_map_surtido_to_domain(m) for m in models]