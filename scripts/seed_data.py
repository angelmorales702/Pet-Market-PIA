#!/usr/bin/env python3
"""Script para generar datos semilla (productos y existencias en dos almacenes, y algunos clientes).

Uso:
    python scripts/seed_data.py

Requiere:
    - Variable de entorno DATABASE_URL configurada
    - Migraciones aplicadas (alembic upgrade head)

El script es idempotente: si un almacén, producto, existencia o cliente ya existe, lo omite.
"""
import os
import sys
from decimal import Decimal

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.domain.aggregates import Almacen, Cliente, Producto
from src.domain.entities import ExistenciaProducto
from src.domain.value_objects import DireccionEntrega, Dinero, Sku
from src.infrastructure.persistence.models import AlmacenModel, ClienteModel, ProductoModel, ExistenciaModel
from src.infrastructure.persistence.repositories import (
    SqlAlchemyRepositorioAlmacen,
    SqlAlchemyRepositorioCliente,
    SqlAlchemyRepositorioProducto,
)
from src.infrastructure.persistence.repositories import _map_existencia_from_domain


def upsert_almacen(session, nombre: str, ubicacion: str) -> Almacen:
    """Crea un almacén si no existe. Retorna el almacén existente o nuevo."""
    almacen_repo = SqlAlchemyRepositorioAlmacen(session)

    # Verificar si ya existe
    almacen_model = session.execute(
        select(AlmacenModel).where(AlmacenModel.nombre == nombre)
    ).scalar_one_or_none()

    if almacen_model:
        from src.infrastructure.persistence.repositories import _map_almacen_to_domain
        return _map_almacen_to_domain(almacen_model)

    # Crear nuevo
    almacen = Almacen.crear(nombre, ubicacion)
    almacen_repo.guardar(almacen)
    session.commit()
    print(f"✓ Almacén creado: {almacen.nombre}")
    return almacen


def upsert_producto(session, sku: str, nombre: str, descripcion: str, precio: Decimal, categoria: str) -> Producto:
    """Crea un producto si no existe. Retorna el producto existente o nuevo."""
    producto_repo = SqlAlchemyRepositorioProducto(session)

    # Verificar si ya existe
    producto_model = session.execute(
        select(ProductoModel).where(ProductoModel.sku == sku)
    ).scalar_one_or_none()

    if producto_model:
        from src.infrastructure.persistence.repositories import _map_producto_to_domain
        return _map_producto_to_domain(producto_model)

    # Crear nuevo
    producto = Producto.crear(
        sku=Sku.of(sku),
        nombre=nombre,
        descripcion=descripcion,
        precio=Dinero(precio, "MXN"),
        categoria=categoria,
    )
    producto_repo.guardar(producto)
    session.commit()
    print(f"✓ Producto creado: {nombre} ({sku})")
    return producto


def upsert_existencia(session, almacen: Almacen, producto: Producto, cantidad: int) -> None:
    """Crea una existencia si no existe. Usa SKU como identificador único por almacén."""
    from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioAlmacen

    # Verificar si ya existe (clave única: almacen_id + sku)
    ex_model = session.execute(
        select(ExistenciaModel).where(
            ExistenciaModel.almacen_id == almacen.id,
            ExistenciaModel.sku == str(producto.sku)
        )
    ).scalar_one_or_none()

    if ex_model:
        # Actualizar cantidad si es diferente
        if ex_model.cantidad_disponible != cantidad:
            ex_model.cantidad_disponible = cantidad
            session.commit()
            print(f"  ↑ Existencia actualizada: {producto.sku} en {almacen.nombre} ({cantidad} unidades)")
        return

    # Crear nueva existencia
    almacen.agregar_existencia(producto.id, producto.sku, cantidad)
    repo_almacen = SqlAlchemyRepositorioAlmacen(session)
    repo_almacen.guardar(almacen)
    session.commit()
    print(f"✓ Existencia creada: {producto.sku} en {almacen.nombre} ({cantidad} unidades)")


def seed_data():
    """Genera datos semilla en la base de datos."""
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db")

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    clientes_ids = []

    try:
        # =========================================================================
        # Crear Almacenes (idempotente)
        # =========================================================================
        print("\n=== Cargando Almacenes ===")

        almacen_norte = upsert_almacen(session, "CDMX Norte", "Ciudad de México")
        almacen_sur = upsert_almacen(session, "Guadalajara", "Jalisco")

        # =========================================================================
        # Crear Productos (idempotente)
        # =========================================================================
        print("\n=== Cargando Productos ===")

        productos_data = [
            ("SKU-00001", "Croquetas Premium Perro", "Alimento premium para perros adultos", Decimal("500.00"), "Alimentos"),
            ("SKU-00002", "Croquetas Premium Gato", "Alimento premium para gatos adultos", Decimal("450.00"), "Alimentos"),
            ("SKU-00003", "Comida Senior Gato", "Alimento especializado para gatos seniors", Decimal("380.00"), "Alimentos"),
            ("SKU-00004", "Comida Senior Perro", "Alimento para perros mayores", Decimal("420.00"), "Alimentos"),
            ("SKU-00005", "Pelota de Tenis", "Juguetes para mascotas", Decimal("150.00"), "Accesorios"),
            ("SKU-00006", "Arbol Pet House", "Juguetes interactivos", Decimal("280.00"), "Accesorios"),
            ("SKU-00007", "Correa Plástica", "Accesorios de entrenamiento", Decimal("95.00"), "Accesorios"),
            ("SKU-00008", "Rascador de Posts", "Accesorios para gatos", Decimal("180.00"), "Accesorios"),
            ("SKU-00009", "Agua Mineral 1L", "Higiene y alimentación", Decimal("25.00"), "Higiene"),
            ("SKU-00010", "Bolsa de Desperdicios", "Higiene", Decimal("75.00"), "Higiene"),
        ]

        productos = {}
        for sku, nombre, descripcion, precio, categoria in productos_data:
            producto = upsert_producto(session, sku, nombre, descripcion, precio, categoria)
            productos[sku] = producto

        # =========================================================================
        # Crear Existencias (idempotente)
        # =========================================================================
        print("\n=== Cargando Existencias ===")

        existencias_config = [
            # CDMX Norte - más productos de higiene y accesorios
            ("SKU-00001", almacen_norte, 100),
            ("SKU-00002", almacen_norte, 80),
            ("SKU-00005", almacen_norte, 50),
            ("SKU-00006", almacen_norte, 30),
            ("SKU-00007", almacen_norte, 100),
            ("SKU-00008", almacen_norte, 40),
            ("SKU-00009", almacen_norte, 200),
            ("SKU-00010", almacen_norte, 150),
            # Guadalajara - más alimentos
            ("SKU-00001", almacen_sur, 150),
            ("SKU-00002", almacen_sur, 120),
            ("SKU-00003", almacen_sur, 90),
            ("SKU-00004", almacen_sur, 110),
        ]

        for sku, almacen, cantidad in existencias_config:
            if sku in productos:
                upsert_existencia(session, almacen, productos[sku], cantidad)

        # =========================================================================
        # Crear Clientes (idempotente)
        # =========================================================================
        print("\n=== Cargando Clientes ===")

        clientes_data = [
            ("Juan Pérez", "juan.perez@email.com", "555-1234", "Calle 1", "100", "Centro", "CDMX", "06600"),
            ("María López", "maria.lopez@email.com", "555-5678", "Av Reforma", "500", "Cuauhtémoc", "CDMX", "06600"),
            ("Carlos García", "carlos.garcia@email.com", "33-1234-5678", "Av Chapultepec", "123", "Polanco", "CDMX", "11500"),
            ("Ana Martínez", "ana.martinez@email.com", "33-8765-4321", "Calle 5", "45", "Centro", "Guadalajara", "44100"),
        ]

        for nombre, email, telefono, calle, numero, colonia, ciudad, cp in clientes_data:
            # Verificar si ya existe
            cliente_model = session.execute(
                select(ClienteModel).where(ClienteModel.email == email)
            ).scalar_one_or_none()

            if cliente_model:
                print(f"  ↔ Cliente existente: {nombre} ({email})")
                clientes_ids.append(str(cliente_model.id))
                continue

            cliente = Cliente.crear(nombre=nombre, email=email, telefono=telefono)
            cliente.agregar_direccion(DireccionEntrega(
                calle=calle,
                numero=numero,
                colonia=colonia,
                ciudad=ciudad,
                codigo_postal=cp,
            ))

            repo_cliente = SqlAlchemyRepositorioCliente(session)
            repo_cliente.guardar(cliente)
            session.commit()
            print(f"✓ Cliente creado: {nombre} ({email})")
            clientes_ids.append(str(cliente.id))

        # =========================================================================
        # Resumen
        # =========================================================================
        print("\n" + "=" * 50)
        print("✓ ¡Datos semilla generados exitosamente!")
        print("=" * 50)
        print(f"\nIDs de Clientes creados/usados:")
        for i, (nombre, email, _, _, _, _, _, _) in enumerate(clientes_data):
            if i < len(clientes_ids):
                print(f"  - {nombre} ({email}): {clientes_ids[i]}")

    except Exception as e:
        print(f"\n❌ Error al generar datos semilla: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_data()