"""Infraestructura - PetMarket.

Implementaciones concretas de puertos:
- Persistencia PostgreSQL con SQLAlchemy 2.0
- Unit of Work
- Migraciones con Alembic
"""
from __future__ import annotations

# Exportar símbolos principales
from .persistence.models import Base
from .persistence.repositories import (
    SqlAlchemyRepositorioAlmacen,
    SqlAlchemyRepositorioCliente,
    SqlAlchemyRepositorioDevolucion,
    SqlAlchemyRepositorioEnvio,
    SqlAlchemyRepositorioPago,
    SqlAlchemyRepositorioPedido,
    SqlAlchemyRepositorioProducto,
    SqlAlchemyRepositorioSurtido,
)
from .persistence.uow import (
    SqlAlchemyOutboxPublisher,
    SqlAlchemyUnitOfWork,
    create_session_factory,
    create_tables,
    drop_tables,
)

__all__ = [
    "Base",
    "SqlAlchemyRepositorioAlmacen",
    "SqlAlchemyRepositorioCliente",
    "SqlAlchemyRepositorioDevolucion",
    "SqlAlchemyRepositorioEnvio",
    "SqlAlchemyRepositorioPago",
    "SqlAlchemyRepositorioPedido",
    "SqlAlchemyRepositorioProducto",
    "SqlAlchemyRepositorioSurtido",
    "SqlAlchemyUnitOfWork",
    "SqlAlchemyOutboxPublisher",
    "create_session_factory",
    "create_tables",
    "drop_tables",
]