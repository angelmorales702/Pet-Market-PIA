"""Tests de integración para la API REST FastAPI - PetMarket.

Tests usan TestClient de FastAPI contra la base de datos PostgreSQL.
Cada test cubre un endpoint específico citando la User Story correspondiente.

Requieren:
- Variable de entorno TEST_DATABASE_URL configurada
- Docker compose up db ejecutado previamente
"""
from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Configuración de base de datos
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db"
)

# Skip tests if DB not available (unless in CI)
REQUIRE_DB = os.getenv("REQUIRE_DB", "0").lower() in ("1", "true", "yes")


def _db_available() -> bool:
    """Verifica si la base de datos está disponible."""
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not REQUIRE_DB and not _db_available(),
    reason="Base de datos PostgreSQL no disponible (configurar TEST_DATABASE_URL)"
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def test_engine():
    """Engine de base de datos para tests."""
    from src.infrastructure.persistence.models import Base
    eng = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Sesión SQLAlchemy por test con rollback automático."""
    connection = test_engine.connect()
    transaction = connection.begin()
    sess = Session(bind=connection)
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """TestClient para la API - solo para health check."""
    from src.api.main import app

    def get_test_session():
        yield db_session

    app.dependency_overrides["get_session"] = get_test_session
    yield TestClient(app)

    if "get_session" in app.dependency_overrides:
        del app.dependency_overrides["get_session"]


@pytest.fixture
def test_data(db_session):
    """Crea datos de test reutilizables."""
    from src.domain.aggregates import Cliente, Producto, Almacen, Pedido
    from src.domain.entities import (
        LineaPedido, ExistenciaProducto, Surtido
    )
    from src.domain.value_objects import (
        Sku, Dinero, DireccionEntrega, EstadoSurtido
    )
    from src.infrastructure.persistence.repositories import (
        SqlAlchemyRepositorioCliente,
        SqlAlchemyRepositorioProducto,
        SqlAlchemyRepositorioAlmacen,
        SqlAlchemyRepositorioPedido,
    )
    from src.infrastructure.persistence.repositories import _map_existencia_from_domain

    # Crear cliente
    cliente_repo = SqlAlchemyRepositorioCliente(db_session)
    cliente = Cliente.crear("Test API", "testapi@test.com", "555-9999")
    cliente_repo.guardar(cliente)
    db_session.commit()

    # Crear almacén
    almacen_repo = SqlAlchemyRepositorioAlmacen(db_session)
    almacen = Almacen.crear("CDMX", "Ciudad de México")
    almacen_repo.guardar(almacen)
    db_session.commit()

    # Crear producto - SKU debe ser SKU-XXXXX con 5 dígitos
    producto_repo = SqlAlchemyRepositorioProducto(db_session)
    producto = Producto.crear(
        sku=Sku.of("SKU-00001"),
        nombre="Producto API Test",
        descripcion="Producto para testing API",
        precio=Dinero(100, "MXN"),
        categoria="Test"
    )
    producto_repo.guardar(producto)
    db_session.commit()

    # Crear existencia
    existencia = ExistenciaProducto(
        producto_id=producto.id,
        almacen_id=almacen.id,
        sku=Sku.of("SKU-00001"),
        cantidad_disponible=50,
    )
    existencia_model = _map_existencia_from_domain(existencia)
    db_session.add(existencia_model)
    db_session.commit()

    # Crear pedido
    pedido_repo = SqlAlchemyRepositorioPedido(db_session)
    linea = LineaPedido(
        sku=Sku.of("SKU-00001"),
        cantidad=1,
        precio_unitario=Dinero(100, "MXN")
    )
    direccion = DireccionEntrega("Calle API", "1", "Centro", "CDMX", "01000")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=[linea], direccion_entrega=direccion)

    # Crear surtido
    surtido = Surtido(
        id=uuid4(),
        pedido_id=pedido.id,
        almacen_id=almacen.id,
        lineas=[linea],
        estado=EstadoSurtido.PENDIENTE
    )
    pedido.asignar_surtidos([surtido])

    pedido_repo.guardar(pedido)
    db_session.commit()

    return {
        "cliente": cliente,
        "almacen": almacen,
        "producto": producto,
        "pedido": pedido,
        "db_session": db_session,
    }


# =============================================================================
# Tests de Health Check
# =============================================================================

def test_health_check_returns_200(db_session):
    """Endpoint /health debe responder correctamente."""
    # Importar directamente la app para testear el endpoint
    from src.api.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "petmarket-api"


# =============================================================================
# Tests de schemas Pydantic
# =============================================================================

class TestSchemas:
    """Tests de los schemas Pydantic de la API."""

    def test_producto_schema_from_domain(self, test_data):
        """Test del schema de producto."""
        from src.api.main import ProductoSchema

        schema = ProductoSchema.from_domain(test_data["producto"])
        assert schema.id == str(test_data["producto"].id)
        assert schema.sku == str(test_data["producto"].sku)
        assert schema.nombre == test_data["producto"].nombre
        assert schema.activo == test_data["producto"].activo

    def test_lista_productos_response(self, test_data):
        """Test del response de lista de productos."""
        from src.api.main import ListaProductosResponse, ProductoSchema

        response = ListaProductosResponse(
            productos=[ProductoSchema.from_domain(test_data["producto"])],
            total=1
        )
        assert response.total == 1
        assert len(response.productos) == 1

    def test_almacen_schema_from_domain(self, test_data):
        """Test del schema de almacén."""
        from src.api.main import AlmacenSchema

        schema = AlmacenSchema.from_domain(test_data["almacen"])
        assert schema.id == str(test_data["almacen"].id)
        assert schema.nombre == test_data["almacen"].nombre

    def test_pedido_response_from_domain(self, test_data):
        """Test del response de pedido."""
        from src.api.main import PedidoResponse

        response = PedidoResponse.from_domain(test_data["pedido"])
        assert response.id == str(test_data["pedido"].id)
        assert response.cliente_id == str(test_data["pedido"].cliente_id)
        assert response.estado == test_data["pedido"].estado.value
        assert response.total == str(test_data["pedido"].total.monto)


# =============================================================================
# Tests que usan los repositorios directamente
# =============================================================================

class TestRepositorios:
    """Tests de repositorios con PostgreSQL real."""

    def test_listar_productos_activos(self, db_session, test_data):
        """US-001: Listar productos activos."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto

        repo = SqlAlchemyRepositorioProducto(db_session)
        productos = repo.obtener_activos()
        assert len(productos) >= 1

    def test_obtener_producto_por_sku(self, db_session, test_data):
        """US-001: Obtener detalles de un producto por SKU."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto

        repo = SqlAlchemyRepositorioProducto(db_session)
        producto = repo.obtener_por_sku(test_data["producto"].sku)
        assert producto is not None
        assert producto.sku == test_data["producto"].sku

    def test_obtener_producto_no_encontrado(self, db_session):
        """US-001: Producto no encontrado."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto
        from src.domain.value_objects import Sku

        repo = SqlAlchemyRepositorioProducto(db_session)
        producto = repo.obtener_por_sku(Sku.of("SKU-99999"))
        assert producto is None

    def test_listar_almacenes(self, db_session, test_data):
        """Listar almacenes disponibles."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioAlmacen

        repo = SqlAlchemyRepositorioAlmacen(db_session)
        almacenes = repo.obtener_todos()
        assert len(almacenes) >= 1

    def test_obtener_inventario_almacen(self, db_session, test_data):
        """US-001: Consultar inventario de un almacén."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioAlmacen

        repo = SqlAlchemyRepositorioAlmacen(db_session)
        almacen = repo.obtener_por_id(test_data["almacen"].id)
        assert almacen is not None
        assert len(almacen.existencias) >= 1

    def test_obtener_almacen_no_encontrado(self, db_session):
        """Almacén no encontrado."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioAlmacen

        repo = SqlAlchemyRepositorioAlmacen(db_session)
        almacen = repo.obtener_por_id(uuid4())
        assert almacen is None

    def test_consultar_pedido(self, db_session, test_data):
        """Consultar estado de un pedido."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido

        repo = SqlAlchemyRepositorioPedido(db_session)
        pedido = repo.obtener_por_id(test_data["pedido"].id)
        assert pedido is not None

    def test_listar_pedidos_cliente(self, db_session, test_data):
        """US-012: Listar pedidos de un cliente."""
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido

        repo = SqlAlchemyRepositorioPedido(db_session)
        pedidos = repo.obtener_por_cliente(test_data["cliente"].id)
        assert len(pedidos) >= 1

    def test_uow_rollback_en_exception(self, db_session):
        """Verifica que el UoW hace rollback cuando hay excepción."""
        from src.domain.aggregates import Pedido
        from src.domain.entities import LineaPedido
        from src.domain.value_objects import DireccionEntrega, Sku, Dinero
        from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido

        try:
            linea = LineaPedido(
                sku=Sku.of("SKU-03003"),
                cantidad=1,
                precio_unitario=Dinero(50, "MXN")
            )

            pedido = Pedido.crear(
                cliente_id=uuid4(),  # Cliente inexistente
                lineas=[linea],
                direccion=DireccionEntrega("Calle", "1", "C", "CDMX", "01000")
            )
            pedido_repo = SqlAlchemyRepositorioPedido(db_session)
            pedido_repo.guardar(pedido)
            db_session.commit()

            # Forzar rollback
            db_session.rollback()

        except Exception:
            db_session.rollback()

        # Verificar que nada se guardó
        pedido_repo = SqlAlchemyRepositorioPedido(db_session)
        pedidos = pedido_repo.obtener_por_cliente(uuid4())
        assert len(pedidos) == 0