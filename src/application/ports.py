"""Puertos (Interfaces) de la capa de aplicación - PetMarket.

Define los contratos que la infraestructura debe implementar.
No importan nada de infraestructura (SQLAlchemy, FastAPI, etc.).

Alineado con ADR-003: Domain Events publicados por casos de uso.
Alineado con 12-Factor App: Configuración vía entorno, no código.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Sequence
from uuid import UUID

from src.domain.aggregates import Almacen, Cliente, Devolucion, Envio, Pago, Pedido, Producto
from src.domain.entities import Surtido
from src.domain.events import DomainEvent
from src.domain.value_objects import Dinero, Guia, Sku

# =============================================================================
# REPOSITORIOS (Read/Write de Aggregates)
# =============================================================================

class RepositorioPedido(ABC):
    """Puerto para persistencia de Pedidos."""

    @abstractmethod
    def guardar(self, pedido: Pedido) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, pedido_id: UUID) -> Optional[Pedido]:
        pass

    @abstractmethod
    def obtener_por_cliente(self, cliente_id: UUID) -> List[Pedido]:
        pass

    @abstractmethod
    def obtener_por_estado(self, estado: str) -> List[Pedido]:
        pass


class RepositorioCliente(ABC):
    """Puerto para persistencia de Clientes."""

    @abstractmethod
    def guardar(self, cliente: Cliente) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, cliente_id: UUID) -> Optional[Cliente]:
        pass

    @abstractmethod
    def obtener_por_email(self, email: str) -> Optional[Cliente]:
        pass


class RepositorioProducto(ABC):
    """Puerto para persistencia de Productos."""

    @abstractmethod
    def guardar(self, producto: Producto) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, producto_id: UUID) -> Optional[Producto]:
        pass

    @abstractmethod
    def obtener_por_sku(self, sku: Sku) -> Optional[Producto]:
        pass

    @abstractmethod
    def obtener_activos(self) -> List[Producto]:
        pass

    @abstractmethod
    def obtener_todos(self) -> List[Producto]:
        pass


class RepositorioAlmacen(ABC):
    """Puerto para persistencia de Almacenes."""

    @abstractmethod
    def guardar(self, almacen: Almacen) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, almacen_id: UUID) -> Optional[Almacen]:
        pass

    @abstractmethod
    def obtener_todos(self) -> List[Almacen]:
        pass


class RepositorioPago(ABC):
    """Puerto para persistencia de Pagos."""

    @abstractmethod
    def guardar(self, pago: Pago) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, pago_id: UUID) -> Optional[Pago]:
        pass

    @abstractmethod
    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Pago]:
        pass


class RepositorioEnvio(ABC):
    """Puerto para persistencia de Envíos."""

    @abstractmethod
    def guardar(self, envio: Envio) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, envio_id: UUID) -> Optional[Envio]:
        pass

    @abstractmethod
    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Envio]:
        pass

    @abstractmethod
    def obtener_por_guia(self, guia: Guia) -> Optional[Envio]:
        pass


class RepositorioDevolucion(ABC):
    """Puerto para persistencia de Devoluciones."""

    @abstractmethod
    def guardar(self, devolucion: Devolucion) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, devolucion_id: UUID) -> Optional[Devolucion]:
        pass

    @abstractmethod
    def obtener_por_pedido(self, pedido_id: UUID) -> Optional[Devolucion]:
        pass


class RepositorioSurtido(ABC):
    """Puerto para persistencia de Surtidos."""

    @abstractmethod
    def guardar(self, surtido: Surtido) -> None:
        pass

    @abstractmethod
    def obtener_por_id(self, surtido_id: UUID) -> Optional[Surtido]:
        pass

    @abstractmethod
    def obtener_por_pedido(self, pedido_id: UUID) -> List[Surtido]:
        pass


# =============================================================================
# UNIT OF WORK (Transacciones)
# =============================================================================

class UnitOfWork(ABC):
    """Puerto para gestión de transacciones (Unit of Work pattern).

    Implementaciones: SQLAlchemyUoW, InMemoryUoW (tests).
    """

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    @abstractmethod
    def commit(self) -> None:
        """Confirma la transacción y publica Domain Events."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Revierte la transacción."""
        pass

    @property
    @abstractmethod
    def pedidos(self) -> RepositorioPedido:
        pass

    @property
    @abstractmethod
    def clientes(self) -> RepositorioCliente:
        pass

    @property
    @abstractmethod
    def productos(self) -> RepositorioProducto:
        pass

    @property
    @abstractmethod
    def almacenes(self) -> RepositorioAlmacen:
        pass

    @property
    @abstractmethod
    def pagos(self) -> RepositorioPago:
        pass

    @property
    @abstractmethod
    def envios(self) -> RepositorioEnvio:
        pass

    @property
    @abstractmethod
    def devoluciones(self) -> RepositorioDevolucion:
        pass

    @property
    @abstractmethod
    def surtidos(self) -> RepositorioSurtido:
        pass


# =============================================================================
# PASARELA DE PAGO (External Service)
# =============================================================================

class ResultadoPago:
    """Resultado de una operación de pago."""
    def __init__(self, aprobado: bool, transaccion_id: Optional[str] = None, motivo: Optional[str] = None):
        self.aprobado = aprobado
        self.transaccion_id = transaccion_id
        self.motivo = motivo


class PasarelaPago(ABC):
    """Puerto para integración con pasarela de pagos externa.

    Implementaciones: StripePasarela, PayPalPasarela, FakePasarela (tests).
    """

    @abstractmethod
    def cobrar(self, monto: Dinero, metodo_pago: str, datos_cliente: dict) -> ResultadoPago:
        """Intenta cobrar el monto. Retorna ResultadoPago."""
        pass

    @abstractmethod
    def reembolsar(self, transaccion_id: str, monto: Dinero) -> ResultadoPago:
        """Procesa un reembolso. Retorna ResultadoPago."""
        pass


# =============================================================================
# PUBLICADOR DE DOMAIN EVENTS (ADR-003)
# =============================================================================

class PublicadorEventos(ABC):
    """Puerto para publicar Domain Events a message broker / outbox.

    Implementaciones: KafkaPublisher, RabbitMQPublisher, OutboxPublisher, InMemoryPublisher.
    """

    @abstractmethod
    def publicar(self, eventos: Sequence[DomainEvent]) -> None:
        """Publica una lista de Domain Events."""
        pass


# =============================================================================
# SERVICIOS DE DOMINIO (Inyectados en casos de uso)
# =============================================================================

class Reloj(ABC):
    """Interfaz para reloj inyectable (tests determinísticos)."""

    @abstractmethod
    def ahora(self) -> datetime:
        pass


class CalendarioDiasHabiles(ABC):
    """Interfaz para cálculo de días hábiles."""

    @abstractmethod
    def agregar_dias_habiles(self, fecha_inicio: datetime, dias: int) -> datetime:
        pass