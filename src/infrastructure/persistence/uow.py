"""Unit of Work implementación para SQLAlchemy 2.0.

Gestiona la transacción y coordina los repositorios.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Optional
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.application.ports import (
    PublicadorEventos,
    RepositorioAlmacen,
    RepositorioCliente,
    RepositorioDevolucion,
    RepositorioEnvio,
    RepositorioPago,
    RepositorioPedido,
    RepositorioProducto,
    RepositorioSurtido,
    UnitOfWork,
)
from src.domain.events import DomainEvent
from .models import Base
from .repositories import (
    SqlAlchemyRepositorioAlmacen,
    SqlAlchemyRepositorioCliente,
    SqlAlchemyRepositorioDevolucion,
    SqlAlchemyRepositorioEnvio,
    SqlAlchemyRepositorioPago,
    SqlAlchemyRepositorioPedido,
    SqlAlchemyRepositorioProducto,
    SqlAlchemyRepositorioSurtido,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Unit of Work para SQLAlchemy con PostgreSQL.

    Implementa el patrón Unit of Work coordinando una sesión SQLAlchemy
    y exponiendo los repositorios tipados.
    """

    def __init__(
        self,
        session_factory: sessionmaker,
        event_publisher: PublicadorEventos,
        existing_session: Optional[Session] = None,
    ):
        self._session_factory = session_factory
        self._session: Optional[Session] = None
        self._event_publisher = event_publisher
        self._committed = False
        self._existing_session = existing_session
        self._own_session = existing_session is None

    @property
    def _publisher(self) -> PublicadorEventos:
        """Propiedad compatibilidad - alias a _event_publisher."""
        return self._event_publisher

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        if self._existing_session:
            self._session = self._existing_session
        else:
            self._session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.rollback()
        elif not self._committed:
            # Si no hubo commit explícito y no hubo error, hacer rollback por seguridad
            self.rollback()
        if self._session and self._own_session:
            self._session.close()
            self._session = None

    def commit(self) -> None:
        """Confirma la transacción y publica Domain Events."""
        if not self._session:
            raise RuntimeError("Unit of Work no está activo (fuera del contexto)")

        # Publicar eventos de dominio de todos los agregados rastreados
        # Los agregados se rastrean vía los repositorios
        self._publicar_eventos()

        self._session.commit()
        self._committed = True

    def rollback(self) -> None:
        """Revierte la transacción."""
        if self._session:
            self._session.rollback()
            self._committed = False

    def _publicar_eventos(self) -> None:
        """Recolecta y publica Domain Events de los agregados modificados."""
        if not self._session:
            return

        # SQLAlchemy rastrea objetos en la sesión; iteramos sobre los objetos "dirty" y "new"
        # Para esto necesitamos acceso a los agregados de dominio.
        # Como los repositorios usan merge(), los objetos de dominio no están en la sesión.
        # En su lugar, los casos de uso son responsables de recolectar eventos antes del commit.
        # Este método es un placeholder para compatibilidad con la interfaz.
        pass

    # Propiedades para repositorios (lazy initialization)
    @property
    def pedidos(self) -> RepositorioPedido:
        return SqlAlchemyRepositorioPedido(self._session)

    @property
    def clientes(self) -> RepositorioCliente:
        return SqlAlchemyRepositorioCliente(self._session)

    @property
    def productos(self) -> RepositorioProducto:
        return SqlAlchemyRepositorioProducto(self._session)

    @property
    def almacenes(self) -> RepositorioAlmacen:
        return SqlAlchemyRepositorioAlmacen(self._session)

    @property
    def pagos(self) -> RepositorioPago:
        return SqlAlchemyRepositorioPago(self._session)

    @property
    def envios(self) -> RepositorioEnvio:
        return SqlAlchemyRepositorioEnvio(self._session)

    @property
    def devoluciones(self) -> RepositorioDevolucion:
        return SqlAlchemyRepositorioDevolucion(self._session)

    @property
    def surtidos(self) -> RepositorioSurtido:
        return SqlAlchemyRepositorioSurtido(self._session)


# =============================================================================
# FACTORÍA DE SESIÓN Y CONFIGURACIÓN DE BASE DE DATOS
# =============================================================================

def create_session_factory(database_url: str) -> sessionmaker:
    """Crea una factoría de sesiones SQLAlchemy configurada para PostgreSQL."""
    engine = create_engine(
        database_url,
        pool_pre_ping=True,  # Verifica conexiones antes de usarlas
        pool_size=10,
        max_overflow=20,
        echo=False,  # Cambiar a True para debugging SQL
    )
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def create_tables(database_url: str) -> None:
    """Crea todas las tablas en la base de datos (para desarrollo/tests sin migraciones)."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)


def drop_tables(database_url: str) -> None:
    """Elimina todas las tablas (solo para tests)."""
    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)


# =============================================================================
# PUBLICADOR DE EVENTOS OUTBOX (para producción)
# =============================================================================

class SqlAlchemyOutboxPublisher(PublicadorEventos):
    """Publicador de Domain Events usando patrón Outbox (transaccional).

    Los eventos se guardan en una tabla outbox dentro de la misma transacción
    que los cambios de negocio. Un proceso separado (relay) los publica al broker.
    """

    def __init__(self, session: Session):
        self._session = session

    def publicar(self, eventos: Sequence[DomainEvent]) -> None:
        # En una implementación completa, aquí se insertarían en tabla outbox
        # Por ahora delegamos al logger o a un publicador real
        for evento in eventos:
            # TODO: Insertar en tabla outbox
            pass