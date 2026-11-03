"""Implementación en memoria (falsos/mocks) para pruebas unitarias de la capa de aplicación.

Permite probar todos los casos de uso con pytest sin infraestructura real.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence
from uuid import UUID

from src.domain.aggregates import Almacen, Cliente, Devolucion, Envio, Pago, Pedido, Producto
from src.domain.entities import Surtido
from src.domain.events import DomainEvent
from src.domain.value_objects import Guia, Sku, Dinero
from .ports import (
    PasarelaPago,
    PublicadorEventos,
    RepositorioAlmacen,
    RepositorioCliente,
    RepositorioDevolucion,
    RepositorioEnvio,
    RepositorioPago,
    RepositorioPedido,
    RepositorioProducto,
    RepositorioSurtido,
    ResultadoPago,
    UnitOfWork,
)


class InMemoryRepositorioPedido(RepositorioPedido):
    def __init__(self):
        self.storage: Dict[UUID, Pedido] = {}

    def guardar(self, pedido: Pedido) -> None:
        self.storage[pedido.id] = pedido

    def obtener_por_id(self, pedido_id: UUID) -> Optional[Pedido]:
        return self.storage.get(pedido_id)

    def obtener_por_cliente(self, cliente_id: UUID) -> List[Pedido]:
        return [p for p in self.storage.values() if p.cliente_id == cliente_id]

    def obtener_por_estado(self, estado: str) -> List[Pedido]:
        return [p for p in self.storage.values() if p.estado.value == estado]


class InMemoryRepositorioCliente(RepositorioCliente):
    def __init__(self):
        self.storage: Dict[UUID, Cliente] = {}

    def guardar(self, cliente: Cliente) -> None:
        self.storage[cliente.id] = cliente

    def obtener_por_id(self, cliente_id: UUID) -> Optional[Cliente]:
        return self.storage.get(cliente_id)

    def obtener_por_email(self, email: str) -> Optional[Cliente]:
        return next((c for c in self.storage.values() if c.email == email), None)


class InMemoryRepositorioProducto(RepositorioProducto):
    def __init__(self):
        self.storage: Dict[UUID, Producto] = {}

    def guardar(self, producto: Producto) -> None:
        self.storage[producto.id] = producto

    def obtener_por_id(self, producto_id: UUID) -> Optional[Producto]:
        return self.storage.get(producto_id)

    def obtener_por_sku(self, sku: Sku) -> Optional[Producto]:
        return next((p for p in self.storage.values() if p.sku == sku), None)

    def obtener_activos(self) -> List[Producto]:
        return [p for p in self.storage.values() if p.activo]


class InMemoryRepositorioAlmacen(RepositorioAlmacen):
    def __init__(self):
        self.storage: Dict[UUID, Almacen] = {}

    def guardar(self, almacen: Almacen) -> None:
        self.storage[almacen.id] = almacen

    def obtener_por_id(self, almacen_id: UUID) -> Optional[Almacen]:
        return self.storage.get(almacen_id)

    def obtener_todos(self) -> List[Almacen]:
        return list(self.storage.values())


class InMemoryRepositorioPago(RepositorioPago):
    def __init__(self):
        self.storage: Dict[UUID, Pago] = {}

    def guardar(self, pago: Pago) -> None:
        self.storage[pago.id] = pago

    def obtener_por_id(self, pago_id: UUID) -> Optional[Pago]:
        return self.storage.get(pago_id)

    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Pago]:
        return next((p for p in self.storage.values() if p.pedido_id == pedido_id), None)


class InMemoryRepositorioEnvio(RepositorioEnvio):
    def __init__(self):
        self.storage: Dict[UUID, Envio] = {}

    def guardar(self, envio: Envio) -> None:
        self.storage[envio.id] = envio

    def obtener_por_id(self, envio_id: UUID) -> Optional[Envio]:
        return self.storage.get(envio_id)

    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Envio]:
        return next((e for e in self.storage.values() if e.pedido_id == pedido_id), None)

    def obtener_por_guia(self, guia: Guia) -> Optional[Envio]:
        return next((e for e in self.storage.values() if e.guia and e.guia.valor == guia.valor), None)


class InMemoryRepositorioDevolucion(RepositorioDevolucion):
    def __init__(self):
        self.storage: Dict[UUID, Devolucion] = {}

    def guardar(self, devolucion: Devolucion) -> None:
        self.storage[devolucion.id] = devolucion

    def obtener_por_id(self, devolucion_id: UUID) -> Optional[Devolucion]:
        return self.storage.get(devolucion_id)

    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Devolucion]:
        return next((d for d in self.storage.values() if d.pedido_id == pedido_id), None)


class InMemoryRepositorioSurtido(RepositorioSurtido):
    def __init__(self):
        self.storage: Dict[UUID, Surtido] = {}

    def guardar(self, surtido: Surtido) -> None:
        self.storage[surtido.id] = surtido

    def obtener_por_id(self, surtido_id: UUID) -> Optional[Surtido]:
        return self.storage.get(surtido_id)

    def obtener_por_pedido(self, pedido_id: UUID) -> List[Surtido]:
        return [s for s in self.storage.values() if s.pedido_id == pedido_id]


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self):
        self._pedidos = InMemoryRepositorioPedido()
        self._clientes = InMemoryRepositorioCliente()
        self._productos = InMemoryRepositorioProducto()
        self._almacenes = InMemoryRepositorioAlmacen()
        self._pagos = InMemoryRepositorioPago()
        self._envios = InMemoryRepositorioEnvio()
        self._devoluciones = InMemoryRepositorioDevolucion()
        self._surtidos = InMemoryRepositorioSurtido()
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "InMemoryUnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    @property
    def pedidos(self) -> RepositorioPedido:
        return self._pedidos

    @property
    def clientes(self) -> RepositorioCliente:
        return self._clientes

    @property
    def productos(self) -> RepositorioProducto:
        return self._productos

    @property
    def almacenes(self) -> RepositorioAlmacen:
        return self._almacenes

    @property
    def pagos(self) -> RepositorioPago:
        return self._pagos

    @property
    def envios(self) -> RepositorioEnvio:
        return self._envios

    @property
    def devoluciones(self) -> RepositorioDevolucion:
        return self._devoluciones

    @property
    def surtidos(self) -> RepositorioSurtido:
        return self._surtidos


class FakePasarelaPago(PasarelaPago):
    def __init__(self, siempre_aprobado: bool = True, motivo_rechazo: str = "Fondos insuficientes"):
        self.siempre_aprobado = siempre_aprobado
        self.motivo_rechazo = motivo_rechazo

    def cobrar(self, monto: Dinero, metodo_pago: str, datos_cliente: dict) -> ResultadoPago:
        if self.siempre_aprobado:
            return ResultadoPago(aprobado=True, transaccion_id="TX-12345")
        return ResultadoPago(aprobado=False, motivo=self.motivo_rechazo)

    def reembolsar(self, transaccion_id: str, monto: Dinero) -> ResultadoPago:
        return ResultadoPago(aprobado=True, transaccion_id="TX-REF-999")


class InMemoryEventPublisher(PublicadorEventos):
    def __init__(self):
        self.eventos_publicados: List[DomainEvent] = []

    def publicar(self, eventos: Sequence[DomainEvent]) -> None:
        self.eventos_publicados.extend(eventos)
