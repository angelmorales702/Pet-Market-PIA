"""Configuración de pytest para tests de integración.

Este archivo contiene los fixtures compartidos por todos los tests.
Lee variables de entorno desde .env si existe.

Requiere:
- TEST_DATABASE_URL configurada (debe terminar en '_test')
- Ejecutar: docker compose up db && alembic upgrade head

IMPORTANTE: Los fixtures crean datos en la base de datos real.
Después de cada test, se ejecuta TRUNCATE para limpiar.
"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from alembic.config import Config
from alembic import command

# Cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# =============================================================================
# Configuración de Base de Datos
# =============================================================================

# Variables de entorno obligatorias para tests
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# Variable para CI: si REQUIRE_DB=1, los tests fallan en lugar de omitirse
REQUIRE_DB = os.getenv("REQUIRE_DB", "0").lower() in ("1", "true", "yes")


def _db_available() -> bool:
    """Verifica si la base de datos está disponible."""
    if not TEST_DATABASE_URL:
        return False
    try:
        engine = create_engine(TEST_DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _run_migrations():
    """Ejecuta migraciones de Alembic sobre la base de datos de test."""
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        return True
    except Exception as e:
        print(f"Error ejecutando migraciones: {e}")
        return False


def _fail_or_skip(message: str):
    """Falla el test si REQUIRE_DB=1, de lo contrario hace skip."""
    if REQUIRE_DB:
        pytest.exit(message)
    pytest.skip(message)


@pytest.fixture(scope="session")
def engine():
    """Engine de base de datos para toda la sesión de tests.

    Ejecuta migraciones de Alembic antes de crear el engine.
    """
    if not TEST_DATABASE_URL:
        _fail_or_skip("TEST_DATABASE_URL no está configurada (requerida en CI)")

    # Validar que sea una BD de testing (impedir tocar petmarket_db)
    if not TEST_DATABASE_URL.endswith("_test"):
        pytest.exit(
            f"ERROR: La base de datos de testing debe terminar en '_test'.\n"
            f"TEST_DATABASE_URL={TEST_DATABASE_URL}\n"
            f"NO se permiten cambios en bases de datos de producción."
        )

    # Verificar que la base de datos exista
    if not _db_available():
        _fail_or_skip(
            f"ERROR: No se pudo conectar a la base de datos de testing.\n"
            f"TEST_DATABASE_URL={TEST_DATABASE_URL}\n"
            f"Ejecutar: docker compose up db && alembic upgrade head"
        )

    # Ejecutar migraciones
    if not _run_migrations():
        _fail_or_skip("Error ejecutando migraciones de Alembic")

    eng = create_engine(TEST_DATABASE_URL)

    yield eng

    # No hacer drop_tables para preservar datos entre sesiones


@pytest.fixture(scope="function")
def session(engine):
    """Sesión SQLAlchemy por test.

    USAGE: Los datos se limpian automáticamente con TRUNCATE antes y después de cada test.
    """
    sess = Session(bind=engine)

    yield sess

    # Rollback en lugar de commit - los datos se limpian con clean_db
    sess.rollback()
    sess.close()


@pytest.fixture(scope="function")
def test_session(session):
    """Alias para session, para compatibilidad con fixtures antiguos."""
    return session


@pytest.fixture(scope="function", autouse=True)
def clean_db(engine):
    """Limpia todas las tablas ANTES de cada test (autouse=True).

    Usa TRUNCATE con RESTART IDENTITY CASCADE.
    SOLO se ejecuta si TEST_DATABASE_URL termina en _test.
    """
    if not (TEST_DATABASE_URL and TEST_DATABASE_URL.endswith("_test")):
        yield
        return

    tables = [
        "clientes", "productos", "almacenes", "direcciones",
        "existencias", "pedidos", "lineas_pedido", "surtidos", "lineas_surtido",
        "pagos", "envios", "intentos_entrega", "devoluciones", "lineas_devolucion"
    ]

    # Limpiar tablas ANTES del test
    with engine.connect() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        for table in tables:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        conn.commit()
        conn.execute(text("SET session_replication_role = DEFAULT"))

    yield  # Ejecutar el test


@pytest.fixture
def db_url():
    """Devuelve la URL de la base de datos de testing."""
    return TEST_DATABASE_URL


@pytest.fixture
def uow(session):
    """Unit of Work con sesión de test.

    Usa SqlAlchemyUnitOfWork con existing_session para testear
    con una sesión ya en transacción.
    """
    from src.application.in_memory import InMemoryEventPublisher
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork

    publisher = InMemoryEventPublisher()
    return SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)


# =============================================================================
# Fixtures de datos base (agregados raíz)
# =============================================================================

@pytest.fixture
def cliente(session):
    """Crea un cliente de test."""
    from src.domain.aggregates import Cliente
    from src.domain.value_objects import DireccionEntrega
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioCliente

    repo = SqlAlchemyRepositorioCliente(session)
    cliente = Cliente.crear("Test Cliente", "test@test.com", "555-1234")
    cliente.agregar_direccion(DireccionEntrega("Calle 1", "100", "Centro", "CDMX", "01000"))
    repo.guardar(cliente)
    session.commit()

    return cliente


@pytest.fixture
def almacen_norte(session):
    """Crea un almacén Norte."""
    from src.domain.aggregates import Almacen
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioAlmacen

    repo = SqlAlchemyRepositorioAlmacen(session)
    almacen = Almacen.crear("CDMX Norte", "Ciudad de México")
    repo.guardar(almacen)
    session.commit()

    return almacen


@pytest.fixture
def almacen_sur(session):
    """Crea un almacén Sur."""
    from src.domain.aggregates import Almacen
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioAlmacen

    repo = SqlAlchemyRepositorioAlmacen(session)
    almacen = Almacen.crear("Guadalajara", "Jalisco")
    repo.guardar(almacen)
    session.commit()

    return almacen


@pytest.fixture
def producto_test(session):
    """Crea un producto de test sin existencias (solo para catálogo)."""
    from src.domain.aggregates import Producto
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto
    from src.domain.value_objects import Dinero

    repo = SqlAlchemyRepositorioProducto(session)
    producto = Producto.crear(
        sku="SKU-00001",
        nombre="Producto Test",
        descripcion="Producto para test",
        precio=Dinero(100, "MXN"),
        categoria="Test"
    )
    repo.guardar(producto)
    session.commit()

    return producto


@pytest.fixture
def producto_test_con_stock(session, almacen_norte):
    """Crea un producto de test con existencias en el almacén."""
    from src.domain.aggregates import Producto, Almacen
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto, SqlAlchemyRepositorioAlmacen
    from src.domain.value_objects import Dinero, Sku

    repo_producto = SqlAlchemyRepositorioProducto(session)
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)

    producto = Producto.crear(
        sku=Sku.of("SKU-00001"),
        nombre="Producto Test",
        descripcion="Producto para test",
        precio=Dinero(100, "MXN"),
        categoria="Test"
    )
    repo_producto.guardar(producto)
    session.commit()

    # Agregar existencia en el almacén
    almacen_norte.agregar_existencia(producto.id, producto.sku, 50)
    repo_almacen.guardar(almacen_norte)
    session.commit()

    return producto


@pytest.fixture
def producto_test_2(session):
    """Crea un segundo producto de test."""
    from src.domain.aggregates import Producto
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto
    from src.domain.value_objects import Dinero

    repo = SqlAlchemyRepositorioProducto(session)
    producto = Producto.crear(
        sku="SKU-00002",
        nombre="Producto Test 2",
        descripcion="Producto 2 para test",
        precio=Dinero(200, "MXN"),
        categoria="Test"
    )
    repo.guardar(producto)
    session.commit()

    return producto


# =============================================================================
# Fixtures de pedidos en estados específicos (US-004, US-003, US-007, US-006, US-010, US-011, US-008)
# =============================================================================

def _crear_pedido_con_stock(session, cliente, almacen, producto, cantidad, sku):
    """Helper: crea pedido con stock reservado usando el flujo del dominio."""
    from src.domain.aggregates import Pedido
    from src.domain.entities import LineaPedido
    from src.domain.value_objects import DireccionEntrega, Dinero, Sku
    from src.domain.services import AsignacionAlmacenService
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido, SqlAlchemyRepositorioAlmacen

    linea = LineaPedido(
        sku=Sku.of(sku),
        cantidad=cantidad,
        precio_unitario=Dinero(producto.precio.monto, producto.precio.moneda)
    )
    direccion = DireccionEntrega("Calle API", "1", "Centro", "CDMX", "01000")

    pedido = Pedido.crear(cliente_id=cliente.id, lineas=[linea], direccion_entrega=direccion)

    asignador = AsignacionAlmacenService()
    surtidos = asignador.asignar(pedido, [almacen], reservar=True)
    pedido.asignar_surtidos(surtidos)

    repo_pedido = SqlAlchemyRepositorioPedido(session)
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)
    repo_pedido.guardar(pedido)
    repo_almacen.guardar(almacen)
    session.commit()

    # Recargar el pedido desde la base de datos para asegurar que los surtidos están sincronizados
    return repo_pedido.obtener_por_id(pedido.id)


@pytest.fixture
def pedido_creado(session, cliente, almacen_norte, producto_test):
    """Fixture: Pedido en estado CREADO (antes de PENDIENTE_PAGO).

    Se usa para tests que necesitan crear un pedido desde cero via API.
    """
    from src.domain.aggregates import Pedido
    from src.domain.entities import LineaPedido
    from src.domain.value_objects import DireccionEntrega, Dinero, Sku
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido

    # Crear pedido directamente en estado CREADO (sin asignar surtidos)
    linea = LineaPedido(
        sku=Sku.of("SKU-00001"),
        cantidad=1,
        precio_unitario=Dinero(100, "MXN")
    )
    direccion = DireccionEntrega("Calle Test", "123", "Centro", "CDMX", "01001")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=[linea], direccion_entrega=direccion)

    SqlAlchemyRepositorioPedido(session).guardar(pedido)
    session.commit()

    return pedido


@pytest.fixture
def pedido_pendiente_pago(session, cliente, almacen_norte, producto_test_2):
    """Fixture: Pedido en estado PENDIENTE_PAGO con stock reservado.

    US-004: Checkout confirmado, stock reservado por 15 min, esperando pago.
    Nota: Este fixture asume que producto_test_2 tiene stock en almacen_norte.
    """
    pedido = _crear_pedido_con_stock(session, cliente, almacen_norte, producto_test_2, 2, "SKU-00002")
    # Verificar que el surtido está en el almacén correcto
    assert len(pedido.surtidos) >= 1, "Pedido debe tener al menos un surtido"
    assert pedido.surtidos[0].almacen_id == almacen_norte.id, "Surtido debe estar en almacén norte"
    return pedido


@pytest.fixture
def pedido_pagado(session, pedido_pendiente_pago, almacen_norte):
    """Fixture: Pedido en estado PAGADO.

    US-003/US-004: Pago aprobado, stock confirmado (descontado), listo para preparación.
    """
    from src.application.in_memory import InMemoryEventPublisher
    from src.application.use_cases import ProcesarPagoUseCase
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
    from src.api.main import FakePasarelaPago
    from sqlalchemy.orm import sessionmaker

    # Procesar pago exitoso usando el caso de uso real
    publisher = InMemoryEventPublisher()
    uow = SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)
    pasarela = FakePasarelaPago()
    use_case = ProcesarPagoUseCase(uow, publisher, pasarela)

    pago = use_case.ejecutar(
        pedido_id=pedido_pendiente_pago.id,
        metodo_pago="TARJETA",
        datos_cliente={}
    )
    session.commit()

    # Recargar pedido actualizado con surtidos explícitamente
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from src.infrastructure.persistence.models import PedidoModel, SurtidoModel, LineaSurtidoModel

    stmt = select(PedidoModel).where(
        PedidoModel.id == pedido_pendiente_pago.id
    ).options(
        selectinload(PedidoModel.surtidos).selectinload(SurtidoModel.lineas),
    )
    model = session.execute(stmt).scalar_one_or_none()

    from src.infrastructure.persistence.repositories import _map_pedido_to_domain
    return _map_pedido_to_domain(model) if model else None


@pytest.fixture
def pedido_en_preparacion(session, pedido_pagado):
    """Fixture: Pedido en estado EN_PREPARACION.

    US-007: Almacén ha iniciado la preparación (picking).
    """
    from src.application.in_memory import InMemoryEventPublisher
    from src.application.use_cases import IniciarYEmpacarSurtidoUseCase
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
    from sqlalchemy.orm import sessionmaker

    publisher = InMemoryEventPublisher()
    uow = SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)
    use_case = IniciarYEmpacarSurtidoUseCase(uow, publisher)

    pedido = use_case.iniciar_preparacion(pedido_pagado.id)
    session.commit()

    # Recargar explícitamente con los surtidos
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from src.infrastructure.persistence.models import PedidoModel, SurtidoModel, LineaSurtidoModel

    stmt = select(PedidoModel).where(PedidoModel.id == pedido.id).options(
        selectinload(PedidoModel.surtidos).selectinload(SurtidoModel.lineas),
    )
    model = session.execute(stmt).scalar_one_or_none()

    from src.infrastructure.persistence.repositories import _map_pedido_to_domain
    return _map_pedido_to_domain(model) if model else None


@pytest.fixture
def pedido_empacado(session, pedido_en_preparacion):
    """Fixture: Pedido en estado EMPACADO (TODOS los surtidos empacados).

    US-007: Todos los surtidos están empacados, listo para envío.
    Usa el almacén del primer surtido del pedido, no asume un almacén fijo.
    """
    from src.application.in_memory import InMemoryEventPublisher
    from src.application.use_cases import IniciarYEmpacarSurtidoUseCase
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
    from sqlalchemy.orm import sessionmaker

    # Obtener el almacén del primer surtido del pedido
    if not pedido_en_preparacion.surtidos:
        raise ValueError("pedido_en_preparacion no tiene surtidos")
    almacen_del_surtido = pedido_en_preparacion.surtidos[0].almacen_id

    publisher = InMemoryEventPublisher()
    uow = SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)
    use_case = IniciarYEmpacarSurtidoUseCase(uow, publisher)

    pedido = use_case.confirmar_empaque_surtido(pedido_en_preparacion.id, almacen_del_surtido)
    session.commit()

    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from src.infrastructure.persistence.models import PedidoModel, SurtidoModel, LineaSurtidoModel

    stmt = select(PedidoModel).where(PedidoModel.id == pedido.id).options(
        selectinload(PedidoModel.surtidos).selectinload(SurtidoModel.lineas),
    )
    model = session.execute(stmt).scalar_one_or_none()
    from src.infrastructure.persistence.repositories import _map_pedido_to_domain
    return _map_pedido_to_domain(model) if model else None


@pytest.fixture
def pedido_enviado(session, pedido_empacado):
    """Fixture: Pedido en estado ENVIADO con guía.

    US-006: Envío generado con guía, en tránsito.
    """
    from src.application.in_memory import InMemoryEventPublisher
    from src.application.use_cases import DespacharPedidoUseCase
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
    from sqlalchemy.orm import sessionmaker

    publisher = InMemoryEventPublisher()
    uow = SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)
    use_case = DespacharPedidoUseCase(uow, publisher)

    envio = use_case.ejecutar(pedido_empacado.id, "GUIA-ENVIO-00001")
    session.commit()

    # Recargar explícitamente con los surtidos
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from src.infrastructure.persistence.models import PedidoModel, SurtidoModel, LineaSurtidoModel

    stmt = select(PedidoModel).where(PedidoModel.id == pedido_empacado.id).options(
        selectinload(PedidoModel.surtidos).selectinload(SurtidoModel.lineas),
    )
    model = session.execute(stmt).scalar_one_or_none()

    from src.infrastructure.persistence.repositories import _map_pedido_to_domain
    return _map_pedido_to_domain(model) if model else None


@pytest.fixture
def pedido_entregado(session, pedido_enviado):
    """Fixture: Pedido en estado ENTREGADO (dentro de 5 días hábiles).

    US-010/US-011: Entrega exitosa registrada.
    """
    from src.application.in_memory import InMemoryEventPublisher
    from src.application.use_cases import RegistrarEntregaUseCase
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
    from sqlalchemy.orm import sessionmaker

    publisher = InMemoryEventPublisher()
    uow = SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)
    use_case = RegistrarEntregaUseCase(uow, publisher)

    envio = use_case.ejecutar(pedido_enviado.id, exitoso=True, observaciones="Entregado en puerta")
    session.commit()

    # Recargar explícitamente con los surtidos
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from src.infrastructure.persistence.models import PedidoModel, SurtidoModel, LineaSurtidoModel

    stmt = select(PedidoModel).where(PedidoModel.id == pedido_enviado.id).options(
        selectinload(PedidoModel.surtidos).selectinload(SurtidoModel.lineas),
    )
    model = session.execute(stmt).scalar_one_or_none()

    from src.infrastructure.persistence.repositories import _map_pedido_to_domain
    return _map_pedido_to_domain(model) if model else None


@pytest.fixture
def pedido_entrega_fallida(session, pedido_enviado):
    """Fixture: Pedido en estado ENTREGA_FALLIDA (2 intentos fallidos).

    US-011: Segundo intento fallido, regresa a almacén.
    """
    from src.application.in_memory import InMemoryEventPublisher
    from src.application.use_cases import RegistrarEntregaUseCase
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
    from sqlalchemy.orm import sessionmaker

    publisher = InMemoryEventPublisher()
    uow = SqlAlchemyUnitOfWork(sessionmaker(bind=session.bind), publisher, existing_session=session)
    use_case = RegistrarEntregaUseCase(uow, publisher)

    # Primer intento fallido
    use_case.ejecutar(pedido_enviado.id, exitoso=False, observaciones="No había nadie")
    # Segundo intento fallido -> ENTREGA_FALLIDA
    use_case.ejecutar(pedido_enviado.id, exitoso=False, observaciones="No se entregó")
    session.commit()

    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioPedido
    return SqlAlchemyRepositorioPedido(session).obtener_por_id(pedido_enviado.id)


@pytest.fixture
def pedido_cancelable(session, cliente, almacen_norte, producto_test_2):
    """Fixture: Pedido en estado PENDIENTE_PAGO que puede ser cancelado por el cliente.

    US-008: Cancelación antes de preparación sin penalización.
    """
    return _crear_pedido_con_stock(session, cliente, almacen_norte, producto_test_2, 1, "SKU-00002")


@pytest.fixture
def producto_sin_stock(session):
    """Fixture: Producto con stock 0 en el almacén.

    Para test_crear_pedido_sin_stock que debe retornar 409.
    """
    from src.domain.aggregates import Producto, Almacen
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto, SqlAlchemyRepositorioAlmacen
    from src.domain.value_objects import Dinero, Sku

    repo_producto = SqlAlchemyRepositorioProducto(session)
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)

    # Crear almacén
    almacen = Almacen.crear("Sin Stock", "Test")
    repo_almacen.guardar(almacen)
    session.commit()

    # Crear producto
    producto = Producto.crear(
        sku=Sku.of("SKU-00003"),
        nombre="Producto Sin Stock",
        descripcion="Producto sin stock para test",
        precio=Dinero(100, "MXN"),
        categoria="Test"
    )
    repo_producto.guardar(producto)
    session.commit()

    # Agregar existencia con 0 cantidad
    almacen.agregar_existencia(producto.id, producto.sku, 0)
    repo_almacen.guardar(almacen)
    session.commit()

    return producto


# Skip tests si DB no disponible (a menos que REQUIRE_DB=1)
pytestmark = pytest.mark.skipif(
    not REQUIRE_DB and not _db_available(),
    reason="Base de datos PostgreSQL no disponible (configurar TEST_DATABASE_URL)"
)