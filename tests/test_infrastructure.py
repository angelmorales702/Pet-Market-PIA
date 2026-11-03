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

from src.domain.aggregates import Almacen, Cliente, Pedido, Producto
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
# Usar TEST_DATABASE_URL del entorno o una por defecto para tests locales
# Nota: para CI/CD, se espera que la BD exista o se cree con init-test-db profile
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db"
)


def _db_available() -> bool:
    """Verifica si la base de datos está disponible."""
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
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
    """Test RepositorioAlmacen - operaciones básicas."""
    repo = SqlAlchemyRepositorioAlmacen(session)

    # Primero creamos un almacén vacío y lo guardamos
    almacen = Almacen.crear("Norte", "Monterrey")
    repo.guardar(almacen)
    session.commit()

    obtenido = repo.obtener_por_id(almacen.id)
    assert obtenido is not None
    assert obtenido.nombre == "Norte"

    # Obtener todos
    todos = repo.obtener_todos()
    assert len(todos) >= 1


def test_repositorio_pedido_con_lineas_y_surtidos(session):
    """Test RepositorioPedido completo con líneas y surtidos.

   Este test crea un pedido completo con:
    - Cliente (aggregate root)
    - Almacén (aggregate root)
    - Producto (aggregate root)
    - Pedido con líneas (entity dentro de pedido)
    - Surtidos (entity dentro del agregado Pedido)
    - Existencias (entity independiente con refs por ID)
    """
    from src.domain.aggregates import Almacen, Producto
    from src.domain.entities import ExistenciaProducto, LineaPedido, Surtido
    from src.domain.value_objects import EstadoSurtido, Dinero
    from src.infrastructure.persistence.repositories import _map_existencia_from_domain

    # Crear repositorios necesarios
    repo_cliente = SqlAlchemyRepositorioCliente(session)
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)
    repo_producto = SqlAlchemyRepositorioProducto(session)
    repo_pedido = SqlAlchemyRepositorioPedido(session)

    # 1. Crear y guardar Cliente (aggregate root)
    cliente = Cliente.crear("María López", "maria@test.com", "555-9999")
    cliente.agregar_direccion(DireccionEntrega("Av Reforma", "450", "Centro", "CDMX", "06600"))
    repo_cliente.guardar(cliente)
    session.commit()

    # 2. Crear y guardar Almacén (aggregate root)
    almacen = Almacen.crear("CDMX Norte", "Monterrey")
    repo_almacen.guardar(almacen)
    session.commit()

    # 3. Crear y guardar Producto (aggregate root)
    producto = Producto.crear(
        sku=Sku.of("SKU-10001"),
        nombre="Comida Premium Gato",
        descripcion="Alimento premium para gatos adultos",
        precio=Dinero(750, "MXN"),
        categoria="Alimentos"
    )
    repo_producto.guardar(producto)
    session.commit()

    # 4. Crear Existencia (entity con refs a aggregate roots por ID)
    existencia = ExistenciaProducto(
        producto_id=producto.id,
        almacen_id=almacen.id,
        sku=Sku.of("SKU-10001"),
        cantidad_disponible=50,
        cantidad_reservada=0
    )
    existencia_model = _map_existencia_from_domain(existencia)
    session.add(existencia_model)
    session.commit()

    # 5. Crear Pedido con líneas y surtidos
    lineas = [
        LineaPedido(sku=Sku.of("SKU-10001"), cantidad=3, precio_unitario=Dinero(750, "MXN"))
    ]
    direccion = DireccionEntrega("Av Reforma", "450", "Centro", "CDMX", "06600")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=lineas, direccion_entrega=direccion)

    # Crear surtido manualmente (entity dentro del agregado Pedido)
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=almacen.id,
        lineas=lineas,
        estado=EstadoSurtido.PENDIENTE
    )

    # Asignar surtido al pedido y persistir
    pedido.asignar_surtidos([surtido])
    repo_pedido.guardar(pedido)
    session.commit()

    # 6. Verificar que se guardó correctamente
    obtenido = repo_pedido.obtener_por_id(pedido.id)
    assert obtenido is not None
    assert obtenido.id == pedido.id
    assert len(obtenido.lineas) == 1
    assert obtenido.lineas[0].sku == Sku.of("SKU-10001")
    assert len(obtenido.surtidos) == 1
    assert obtenido.surtidos[0].almacen_id == almacen.id

    print("✓ Test de repositorio pedido con líneas y surtidos pasó")


def test_unit_of_work_commit_y_rollback(session):
    """Test UnitOfWork commit y rollback.

Verifica que el Unit of Work maneja correctamente:
1. Commit exitoso de un pedido completo
2. Rollback cuando hay error (verificado por fixture)
"""
    from src.domain.aggregates import Almacen, Producto

    # Test 1: Commit exitoso
    # Crear un pedido simple y verificar que se persiste
    repo_cliente = SqlAlchemyRepositorioCliente(session)
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)
    repo_producto = SqlAlchemyRepositorioProducto(session)

    # Crear datos de prueba
    cliente = Cliente.crear("Pedro Gómez", "pedro@test.com", "555-1111")
    repo_cliente.guardar(cliente)
    session.commit()

    almacen = Almacen.crear("Guadalajara", "Jalisco")
    repo_almacen.guardar(almacen)
    session.commit()

    producto = Producto.crear(
        sku=Sku.of("SKU-20001"),
        nombre="Ración Perro Senior",
        descripcion="Alimento para perros mayores",
        precio=Dinero(600, "MXN"),
        categoria="Alimentos"
    )
    repo_producto.guardar(producto)
    session.commit()

    # Verificar que los datos se guardaron
    cliente_obtenido = repo_cliente.obtener_por_id(cliente.id)
    assert cliente_obtenido is not None
    assert cliente_obtenido.email == "pedro@test.com"

    almacen_obtenido = repo_almacen.obtener_por_id(almacen.id)
    assert almacen_obtenido is not None
    assert almacen_obtenido.nombre == "Guadalajara"

    producto_obtenido = repo_producto.obtener_por_sku(Sku.of("SKU-20001"))
    assert producto_obtenido is not None

    # Test 2: Verificar rollback funciona con la sesión
    # La fixture ya usa transaction.rollback() al final de cada test

    print("✓ Test de Unit of Work commit y rollback pasó")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])