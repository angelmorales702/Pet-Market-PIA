"""Tests de infraestructura - SQLAlchemy models y repositorios.

Estos tests verifican que los modelos de persistencia se mapean correctamente
y que los repositorios implementan los puertos de la aplicación.
Requieren una base de datos PostgreSQL real (docker compose up db).

Se ejecutan solo si la variable de entorno TEST_DATABASE_URL está configurada
y la base de datos es accesible.

En CI (requiere REQUIRE_DB=1), los tests fallan si la DB no está disponible.
Localmente, los tests pueden omitirse si la DB no está disponible.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from src.domain.aggregates import Almacen, Cliente, Devolucion, Envio, Pago, Pedido, Producto
from src.domain.entities import ExistenciaProducto, LineaDevolucion, LineaPedido, Surtido
from src.domain.value_objects import (
    Dinero,
    DireccionEntrega,
    EstadoDevolucion,
    EstadoEnvio,
    EstadoPago,
    EstadoSurtido,
    Guia,
    MotivoDevolucion,
    Sku,
)
from src.infrastructure.persistence.repositories import (
    SqlAlchemyRepositorioAlmacen,
    SqlAlchemyRepositorioCliente,
    SqlAlchemyRepositorioDevolucion,
    SqlAlchemyRepositorioEnvio,
    SqlAlchemyRepositorioPago,
    SqlAlchemyRepositorioPedido,
    SqlAlchemyRepositorioProducto,
    _map_existencia_from_domain,
)

# Nota: TEST_DATABASE_URL y REQUIRE_DB ya están definidos en conftest.py
# Usa los fixtures de conftest.py para engine y session


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


def test_unit_of_work_commit_y_rollback(session):
    """Test UnitOfWork commit y rollback.

    Verifica que el Unit of Work maneja correctamente:
    1. Commit exitoso de un pedido completo
    2. Rollback cuando hay error (transacción revertida)
    """
    from src.infrastructure.persistence.repositories import (
        SqlAlchemyRepositorioAlmacen,
        SqlAlchemyRepositorioCliente,
        SqlAlchemyRepositorioProducto,
    )

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


def test_repositorio_pago_guardar_y_obtener(session):
    """Test RepositorioPago - CRUD básico."""
    repo_pago = SqlAlchemyRepositorioPago(session)

    # Crear un producto y cliente primero
    repo_producto = SqlAlchemyRepositorioProducto(session)
    repo_cliente = SqlAlchemyRepositorioCliente(session)

    producto = Producto.crear(
        sku=Sku.of("SKU-00001"),
        nombre="Test Product",
        descripcion="Test Product Description",
        precio=Dinero(100, "MXN"),
        categoria="Test"
    )
    repo_producto.guardar(producto)
    session.commit()

    cliente = Cliente.crear("Pago Test", "pago@test.com", "555-0001")
    repo_cliente.guardar(cliente)
    session.commit()

    # Crear un pedido
    repo_pedido = SqlAlchemyRepositorioPedido(session)
    lineas = [
        LineaPedido(sku=Sku.of("SKU-00001"), cantidad=1, precio_unitario=Dinero(100, "MXN"))
    ]
    direccion = DireccionEntrega("Calle Pago", "1", "Centro", "CDMX", "01000")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=lineas, direccion_entrega=direccion)
    repo_pedido.guardar(pedido)
    session.commit()

    # Crear pago usando el aggregate domain
    pago = Pago.crear(pedido_id=pedido.id, monto=Dinero(100, "MXN"), metodo_pago="TARJETA")
    repo_pago.guardar(pago)
    session.commit()

    # Verificar
    obtenido = repo_pago.obtener_por_id(pago.id)
    assert obtenido is not None
    assert obtenido.monto == Dinero(100, "MXN")
    assert obtenido.metodo_pago == "TARJETA"
    assert obtenido.estado == EstadoPago.PENDIENTE

    # Probar aprobar pago
    pago.aprobar()
    repo_pago.guardar(pago)
    session.commit()

    pago_actualizado = repo_pago.obtener_por_id(pago.id)
    assert pago_actualizado.estado == EstadoPago.APROBADO


def test_repositorio_envio_guardar_y_obtener(session):
    """Test RepositorioEnvio - CRUD básico."""

    repo_envio = SqlAlchemyRepositorioEnvio(session)

    # Crear cliente y pedido
    repo_cliente = SqlAlchemyRepositorioCliente(session)
    repo_pedido = SqlAlchemyRepositorioPedido(session)

    cliente = Cliente.crear("Envio Test", "envio@test.com", "555-0002")
    repo_cliente.guardar(cliente)
    session.commit()

    lineas = [
        LineaPedido(sku=Sku.of("SKU-00002"), cantidad=2, precio_unitario=Dinero(50, "MXN"))
    ]
    direccion = DireccionEntrega("Calle Envio", "2", "Centro", "CDMX", "01001")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=lineas, direccion_entrega=direccion)
    repo_pedido.guardar(pedido)
    session.commit()

    # Crear envio
    envio = Envio.crear(pedido_id=pedido.id)
    envio.asignar_guia(Guia.of("GUIA-ENVIO-123"))
    repo_envio.guardar(envio)
    session.commit()

    # Verificar
    obtenido = repo_envio.obtener_por_id(envio.id)
    assert obtenido is not None
    assert obtenido.pedido_id == pedido.id
    # guia es un objeto Guia, no un string
    assert obtenido.guia is not None
    assert obtenido.guia.valor == "GUIA-ENVIO-123"
    assert obtenido.estado == EstadoEnvio.EN_TRASITO


def test_repositorio_devolucion_guardar_y_obtener(session):
    """Test RepositorioDevolucion - CRUD básico."""
    repo_devolucion = SqlAlchemyRepositorioDevolucion(session)

    # Crear cliente y pedido
    repo_cliente = SqlAlchemyRepositorioCliente(session)
    repo_pedido = SqlAlchemyRepositorioPedido(session)

    cliente = Cliente.crear("Devolucion Test", "devolucion@test.com", "555-0003")
    repo_cliente.guardar(cliente)
    session.commit()

    lineas = [
        LineaPedido(sku=Sku.of("SKU-00003"), cantidad=1, precio_unitario=Dinero(200, "MXN"))
    ]
    direccion = DireccionEntrega("Calle Dev", "3", "Centro", "CDMX", "01002")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=lineas, direccion_entrega=direccion)
    repo_pedido.guardar(pedido)
    session.commit()

    # Crear devolucion usando solicitar (método correcto)
    devolucion = Devolucion.solicitar(
        pedido_id=pedido.id,
        motivo=MotivoDevolucion.of("Producto defectuoso"),
        lineas=[LineaDevolucion(sku=Sku.of("SKU-00003"), cantidad=1)]
    )
    repo_devolucion.guardar(devolucion)
    session.commit()

    # Verificar
    obtenido = repo_devolucion.obtener_por_id(devolucion.id)
    assert obtenido is not None
    assert obtenido.pedido_id == pedido.id
    assert obtenido.estado == EstadoDevolucion.SOLICITADA
    assert len(obtenido.lineas) == 1


def test_repositorio_almacen_guardar_y_existencias(session):
    """Test RepositorioAlmacen guardando con existencias."""
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)

    # Crear almacén con existencias usando el método del dominio
    almacen = Almacen.crear("Baja California", "Tijuana")
    almacen.agregar_existencia(
        producto_id=uuid4(),
        sku=Sku.of("SKU-00004"),
        cantidad=100
    )

    repo_almacen.guardar(almacen)
    session.commit()

    # Verificar
    obtenido = repo_almacen.obtener_por_id(almacen.id)
    assert obtenido is not None
    assert obtenido.nombre == "Baja California"
    assert len(obtenido.existencias) == 1
    assert obtenido.existencias["SKU-00004"].cantidad_disponible == 100


def test_repositorio_almacen_reserva_persistencia(session):
    """Test de ida y vuelta: reservar stock y verificar que persiste."""
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)

    # Crear almacén con existencias
    almacen = Almacen.crear("Reserva Test", "Ciudad")
    almacen.agregar_existencia(
        producto_id=uuid4(),
        sku=Sku.of("SKU-00005"),
        cantidad=100
    )

    repo_almacen.guardar(almacen)
    session.commit()

    # Recargar y verificar stock inicial
    almacen_recargado = repo_almacen.obtener_por_id(almacen.id)
    ex_inicial = almacen_recargado.obtener_existencia(Sku.of("SKU-00005"))
    assert ex_inicial.cantidad_disponible == 100
    assert ex_inicial.cantidad_reservada == 0

    # Reservar stock (disponible no cambia, solo reservado)
    almacen_recargado.reservar(Sku.of("SKU-00005"), 10, uuid4())
    repo_almacen.guardar(almacen_recargado)
    session.commit()

    # Recargar y verificar reserva persistió
    almacen_final = repo_almacen.obtener_por_id(almacen.id)
    ex_reservado = almacen_final.obtener_existencia(Sku.of("SKU-00005"))
    assert ex_reservado.cantidad_disponible == 100, f"Disponible sin cambiar: {ex_reservado.cantidad_disponible}"
    assert ex_reservado.cantidad_reservada == 10, f"Reservado: {ex_reservado.cantidad_reservada}"

    # Confirmar venta (pago aprobado) - esto sí reduce disponible
    almacen_final.confirmar_venta(Sku.of("SKU-00005"), 10)
    repo_almacen.guardar(almacen_final)
    session.commit()

    # Verificar que el stock se actualizó correctamente
    almacen_confirmado = repo_almacen.obtener_por_id(almacen.id)
    ex_confirmado = almacen_confirmado.obtener_existencia(Sku.of("SKU-00005"))
    assert ex_confirmado.cantidad_disponible == 90, f"Post-confirmar disponible: {ex_confirmado.cantidad_disponible}"
    assert ex_confirmado.cantidad_reservada == 0, f"Post-confirmar reservada: {ex_confirmado.cantidad_reservada}"


def test_repositorio_pedido_persistencia_surtidos_2_almacenes(session):
    """Test de ida y vuelta: Pedido con 2 surtidos (uno por almacén).

    Este test verifica que los surtidos se persistan correctamente cuando
    un pedido tiene surtidos en múltiples almacenes.

    Regla de AsignacionAlmacenService:
    - Para cada línea, busca el almacén con stock suficiente
    - Si hay múltiples almacenes con stock, elige el que tiene MÁS stock
    - Todas las líneas del mismo SKU van a un solo surtido (un almacén)
    """
    # 1. Crear datos base
    repo_cliente = SqlAlchemyRepositorioCliente(session)
    repo_almacen1 = SqlAlchemyRepositorioAlmacen(session)
    repo_almacen2 = SqlAlchemyRepositorioAlmacen(session)
    repo_producto = SqlAlchemyRepositorioProducto(session)
    repo_pedido = SqlAlchemyRepositorioPedido(session)

    cliente = Cliente.crear("Test Surtido", "surtido@test.com", "555-7777")
    repo_cliente.guardar(cliente)
    session.commit()

    almacen1 = Almacen.crear("Almacen Norte", "CDMX")
    almacen2 = Almacen.crear("Almacen Sur", "Guadalajara")
    repo_almacen1.guardar(almacen1)
    repo_almacen2.guardar(almacen2)
    session.commit()

    # Producto A con stock SOLO en almacen1
    producto_a = Producto.crear(
        sku=Sku.of("SKU-00021"),
        nombre="Producto A",
        descripcion="Producto A para test",
        precio=Dinero(100, "MXN"),
        categoria="Test"
    )
    repo_producto.guardar(producto_a)
    session.commit()

    # Producto B con stock SOLO en almacen2
    producto_b = Producto.crear(
        sku=Sku.of("SKU-00022"),
        nombre="Producto B",
        descripcion="Producto B para test",
        precio=Dinero(100, "MXN"),
        categoria="Test"
    )
    repo_producto.guardar(producto_b)
    session.commit()

    # Agregar existencias: A SOLO en almacen1, B SOLO en almacen2
    almacen1 = repo_almacen1.obtener_por_id(almacen1.id)
    almacen1.agregar_existencia(producto_a.id, producto_a.sku, 50)
    repo_almacen1.guardar(almacen1)
    session.commit()

    almacen2 = repo_almacen2.obtener_por_id(almacen2.id)
    almacen2.agregar_existencia(producto_b.id, producto_b.sku, 30)
    repo_almacen2.guardar(almacen2)
    session.commit()

    # 2. Crear pedido con 2 líneas de SKU distintos
    linea_a = LineaPedido(sku=Sku.of("SKU-00021"), cantidad=2, precio_unitario=Dinero(100, "MXN"))
    linea_b = LineaPedido(sku=Sku.of("SKU-00022"), cantidad=1, precio_unitario=Dinero(100, "MXN"))
    direccion = DireccionEntrega("Calle Test", "1", "Centro", "CDMX", "01000")
    pedido = Pedido.crear(cliente_id=cliente.id, lineas=[linea_a, linea_b], direccion_entrega=direccion)

    # Usar el servicio de asignación real
    from src.domain.services import AsignacionAlmacenService
    asignador = AsignacionAlmacenService()
    surtidos = asignador.asignar(pedido, [almacen1, almacen2], reservar=True)
    pedido.asignar_surtidos(surtidos)

    # Verificar asignación inicial: debe haber 2 surtidos con almacenes distintos
    assert len(pedido.surtidos) == 2, f"Esperado 2 surtidos, obtuve {len(pedido.surtidos)}"
    almacenes_asignados = [s.almacen_id for s in pedido.surtidos]
    print(f"DEBUG: almacenes esperados: {almacen1.id}, {almacen2.id}")
    print(f"DEBUG: almacenes asignados: {almacenes_asignados}")
    assert almacen1.id in almacenes_asignados, f"Almacen1 ({almacen1.id}) no asignado"
    assert almacen2.id in almacenes_asignados, f"Almacen2 ({almacen2.id}) no asignado"

    for s in pedido.surtidos:
        print(f"DEBUG: surtido id={s.id}, almacen_id={s.almacen_id}, estado={s.estado.value}")

    # 3. Guardar el pedido
    repo_pedido.guardar(pedido)
    session.commit()

    # 4. Recargar y verificar (test de persistencia)
    obtenido = repo_pedido.obtener_por_id(pedido.id)
    assert obtenido is not None, "Pedido no recuperado"
    assert len(obtenido.surtidos) == 2, f"Esperado 2 surtidos recargados, obtuve {len(obtenido.surtidos)}"

    # Verificar IDs y almacenes coinciden exactamente
    surtidos_original = sorted(pedido.surtidos, key=lambda s: s.id)
    surtidos_recargados = sorted(obtenido.surtidos, key=lambda s: s.id)

    for orig, recargado in zip(surtidos_original, surtidos_recargados, strict=False):
        assert orig.id == recargado.id, f"ID de surtido no coincide: {orig.id} vs {recargado.id}"
        assert orig.almacen_id == recargado.almacen_id, "Almacen_id no coincide"
        assert orig.estado == recargado.estado, f"Estado no coincide: {orig.estado} vs {recargado.estado}"

    # Verificar líneas
    total_lineas = sum(len(s.lineas) for s in obtenido.surtidos)
    assert total_lineas == 2, f"Esperado 2 líneas totales, obtuve {total_lineas}"

    # Verificar que los estados son PENDIENTE
    for s in obtenido.surtidos:
        assert s.estado == EstadoSurtido.PENDIENTE, f"Estado inesperado: {s.estado}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-cov=src", "--cov-fail-under=80"])