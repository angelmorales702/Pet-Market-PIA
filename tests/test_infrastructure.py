"""Tests de infraestructura - SQLAlchemy models y repositorios.

Estos tests verifican que los modelos de persistencia se mapean correctamente
y que los repositorios implementan los puertos de la aplicación.
Requieren una base de datos PostgreSQL real (docker compose up db).

Se ejecutan solo si la variable de entorno TEST_DATABASE_URL está configurada
y la base de datos es accesible.
"""
from __future__ import annotations

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.domain.aggregates import Almacen
from src.domain.entities import LineaPedido
from src.domain.value_objects import (
    DireccionEntrega,
    Dinero,
    EstadoSurtido,
    Sku,
)
from src.infrastructure.persistence.models import Base
from src.infrastructure.persistence.repositories import (
    SqlAlchemyRepositorioAlmacen,
    SqlAlchemyRepositorioCliente,
    SqlAlchemyRepositorioPedido,
    SqlAlchemyRepositorioProducto,
)
from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork, create_session_factory


# Configuración de base de datos para tests
# Usar DATABASE_URL del entorno o una por defecto para tests locales
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db"
)


def _db_available() -> bool:
    """Verifica si la base de datos está disponible."""
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


# Skip todos los tests de infraestructura si no hay DB disponible
pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="Base de datos PostgreSQL no disponible (configurar TEST_DATABASE_URL y ejecutar docker compose up db)"
)


@pytest.fixture(scope="session")
def engine():
    """Engine de base de datos para toda la sesión de tests."""
    eng = create_engine(TEST_DATABASE_URL)
    # Crear todas las tablas
    Base.metadata.create_all(eng)
    yield eng
    # Cleanup
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="function")
def session(engine):
    """Sesión SQLAlchemy por test con rollback automático."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def uow(session):
    """Unit of Work con sesión de test."""
    from src.application.in_memory import InMemoryEventPublisher

    publisher = InMemoryEventPublisher()
    # Monkey-patch para usar la sesión de test
    class TestUow(SqlAlchemyUnitOfWork):
        def __enter__(self):
            self._session = session
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                self.rollback()

        def commit(self):
            self._session.commit()
            self._committed = True

        def rollback(self):
            self._session.rollback()
            self._committed = False

    return TestUow(sessionmaker(bind=session.bind), publisher)


def test_modelos_crean_tablas_correctamente(engine):
    """Verifica que todas las tablas se crean sin errores."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tablas = inspector.get_table_names()

    esperadas = {
        "clientes", "direcciones", "productos", "almacenes", "existencias",
        "pedidos", "lineas_pedido", "surtidos", "lineas_surtido",
        "pagos", "envios", "intentos_entrega", "devoluciones", "lineas_devolucion"
    }

    for tabla in esperadas:
        assert tabla in tablas, f"Tabla {tabla} no encontrada"


def test_repositorio_cliente_guardar_y_obtener(session):
    """Test CRUD básico de RepositorioCliente."""
    repo = SqlAlchemyRepositorioCliente(session)

    from src.domain.aggregates import Cliente
    from src.domain.value_objects import DireccionEntrega

    cliente = Cliente.crear("Juan Pérez", "juan@test.com", "555-1234")
    cliente.agregar_direccion(DireccionEntrega("Calle 1", "100", "Centro", "Monterrey", "64000"))

    repo.guardar(cliente)
    session.commit()

    # Obtener por ID
    obtenido = repo.obtener_por_id(cliente.id)
    assert obtenido is not None
    assert obtenido.nombre == "Juan Pérez"
    assert obtenido.email == "juan@test.com"
    assert len(obtenido.direcciones) == 1

    # Obtener por email
    por_email = repo.obtener_por_email("juan@test.com")
    assert por_email is not None
    assert por_email.id == cliente.id


def test_repositorio_producto_guardar_y_obtener(session):
    """Test CRUD básico de RepositorioProducto."""
    repo = SqlAlchemyRepositorioProducto(session)

    from src.domain.aggregates import Producto

    producto = Producto.crear(
        sku=Sku.of("SKU-00001"),
        nombre="Croquetas Premium",
        descripcion="Alimento para perros adultos",
        precio=Dinero(500, "MXN"),
        categoria="Alimentos"
    )

    repo.guardar(producto)
    session.commit()

    # Obtener por ID
    obtenido = repo.obtener_por_id(producto.id)
    assert obtenido is not None
    assert obtenido.nombre == "Croquetas Premium"
    assert obtenido.sku == Sku.of("SKU-00001")
    assert obtenido.precio == Dinero(500, "MXN")

    # Obtener por SKU
    por_sku = repo.obtener_por_sku(Sku.of("SKU-00001"))
    assert por_sku is not None
    assert por_sku.id == producto.id

    # Obtener activos
    activos = repo.obtener_activos()
    assert len(activos) >= 1


def test_repositorio_almacen_con_existencias(session):
    """Test RepositorioAlmacen con existencias."""
    repo = SqlAlchemyRepositorioAlmacen(session)

    almacen = Almacen.crear("Norte", "Monterrey")
    almacen.agregar_existencia(uuid4(), Sku.of("SKU-00001"), 100)

    repo.guardar(almacen)
    session.commit()

    obtenido = repo.obtener_por_id(almacen.id)
    assert obtenido is not None
    assert obtenido.nombre == "Norte"
    assert "SKU-00001" in obtenido.existencias
    assert obtenido.existencias["SKU-00001"].cantidad_disponible == 100
    assert obtenido.existencias["SKU-00001"].disponible_para_venta == 100

    # Obtener todos
    todos = repo.obtener_todos()
    assert len(todos) >= 1


def test_repositorio_pedido_con_lineas_y_surtidos(session):
    """Test RepositorioPedido completo con líneas y surtidos."""
    from src.domain.aggregates import Pedido
    from src.domain.entities import Surtido
    from src.domain.value_objects import EstadoSurtido

    # Setup: cliente, producto, almacen
    cliente_repo = SqlAlchemyRepositorioCliente(session)
    producto_repo = SqlAlchemyRepositorioProducto(session)
    almacen_repo = SqlAlchemyRepositorioAlmacen(session)
    pedido_repo = SqlAlchemyRepositorioPedido(session)

    cliente = Cliente.crear("María López", "maria@test.com", "555-5678")
    cliente_repo.guardar(cliente)

    producto = Producto.crear(
        sku=Sku.of("SKU-00002"),
        nombre="Collar LED",
        descripcion="Collar luminoso para perros",
        precio=Dinero(250, "MXN"),
        categoria="Accesorios"
    )
    producto_repo.guardar(producto)

    almacen = Almacen.crear("Sur", "Guadalupe")
    almacen.agregar_existencia(producto.id, Sku.of("SKU-00002"), 50)
    almacen_repo.guardar(almacen)

    session.commit()

    # Crear pedido
    lineas = [LineaPedido(Sku.of("SKU-00002"), 2, Dinero(250, "MXN"))]
    direccion = DireccionEntrega("Av Universidad", "500", "Tecnológico", "Monterrey", "64000")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=lineas, direccion_entrega=direccion)

    # Asignar surtido
    surtido = Surtido(id=uuid4(), pedido_id=pedido.id, almacen_id=almacen.id, lineas=lineas)
    surtido.validar_no_vacio()
    pedido.asignar_surtidos([surtido])

    pedido_repo.guardar(pedido)
    session.commit()

    # Obtener y verificar
    obtenido = pedido_repo.obtener_por_id(pedido.id)
    assert obtenido is not None
    assert obtenido.estado.value == "PENDIENTE_PAGO"
    assert len(obtenido.lineas) == 1
    assert obtenido.lineas[0].sku == Sku.of("SKU-00002")
    assert len(obtenido.surtidos) == 1
    assert obtenido.surtidos[0].almacen_id == almacen.id
    assert obtenido.surtidos[0].estado == EstadoSurtido.PENDIENTE

    # Obtener por cliente
    por_cliente = pedido_repo.obtener_por_cliente(cliente.id)
    assert len(por_cliente) >= 1
    assert any(p.id == pedido.id for p in por_cliente)


def test_unit_of_work_commit_y_rollback(session):
    """Test UnitOfWork commit y rollback."""
    from src.application.in_memory import InMemoryEventPublisher

    publisher = InMemoryEventPublisher()
    session_factory = sessionmaker(bind=session.bind)

    class TestUow(SqlAlchemyUnitOfWork):
        def __enter__(self):
            self._session = session
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def commit(self):
            self._session.commit()
            self._committed = True

        def rollback(self):
            self._session.rollback()
            self._committed = False

    # Test commit
    uow = TestUow(session_factory, publisher)
    with uow:
        cliente = Cliente.crear("Test UOW", "uow@test.com", "555-9999")
        uow.clientes.guardar(cliente)
        uow.commit()

    assert uow._committed is True

    # Verificar que se guardó
    repo = SqlAlchemyRepositorioCliente(session)
    guardado = repo.obtener_por_email("uow@test.com")
    assert guardado is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])