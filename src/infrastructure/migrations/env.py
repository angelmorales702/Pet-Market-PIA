"""Entorno de migraciones Alembic para PetMarket.

Configura el contexto de migración usando los modelos SQLAlchemy
y la URL de base de datos desde variables de entorno.
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Añadir el directorio raíz del proyecto al path para importar modelos
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importar modelos para que Base.metadata esté poblado
from src.infrastructure.persistence.models import Base  # noqa: E402

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata para autogenerate
target_metadata = Base.metadata


def get_database_url() -> str:
    """Obtiene la URL de base de datos desde variable de entorno o config."""
    # Prioridad: ENV var > alembic.ini
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Esto configura el contexto solo con una URL y no requiere un Engine.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Crea un Engine y asocia una conexión al contexto.
    """
    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        configuration = {}

    # Sobrescribir URL con variable de entorno si existe
    database_url = get_database_url()
    configuration["sqlalchemy.url"] = database_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Incluir enums en migraciones
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()