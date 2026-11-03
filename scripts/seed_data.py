#!/usr/bin/env python3
"""Script para generar datos semilla (productos y existencias en dos almacenes, y algunos clientes).

Uso:
    python scripts/seed_data.py

Requiere:
    - Variable de entorno DATABASE_URL configurada
    - Migraciones aplicadas (alembic upgrade head)
"""
import os
import sys
from decimal import Decimal

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.domain.aggregates import Almacen, Cliente, Producto
from src.domain.entities import ExistenciaProducto
from src.domain.value_objects import DireccionEntrega, Dinero, Sku
from src.infrastructure.persistence.models import Base
from src.infrastructure.persistence.repositories import (
    SqlAlchemyRepositorioAlmacen,
    SqlAlchemyRepositorioCliente,
    SqlAlchemyRepositorioProducto,
)
from src.infrastructure.persistence.repositories import _map_existencia_from_domain, _map_almacen_from_domain


def seed_data():
    """Genera datos semilla en la base de datos."""
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://petmarket_user:petmarket_pass@localhost:5432/petmarket_db")

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Crear almacenes
        almacenes = [
            Almacen.crear("CDMX Norte", "Ciudad de México"),
            Almacen.crear("Guadalajara", "Jalisco"),
        ]

        for almacen in almacenes:
            repo_almacen = SqlAlchemyRepositorioAlmacen(session)
            repo_almacen.guardar(almacen)
            session.commit()
            print(f"✓ Almacén creado: {almacen.nombre}")

        # Crear productos
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

        for sku, nombre, descripcion, precio, categoria in productos_data:
            producto = Producto.crear(
                sku=Sku.of(sku),
                nombre=nombre,
                descripcion=descripcion,
                precio=Dinero(precio, "MXN"),
                categoria=categoria,
            )
            # Usar el repositorio para guardar
            from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioProducto
            repo_producto = SqlAlchemyRepositorioProducto(session)
            repo_producto.guardar(producto)
            session.commit()
            print(f"✓ Producto creado: {nombre} ({sku})")

        # Crear existencias para cada almacén
        existencias = [
            # CDMX Norte - más productos de higiene y accesorios
            ("SKU-00001", 100, "CDMX Norte"),
            ("SKU-00002", 80, "CDMX Norte"),
            ("SKU-00005", 50, "CDMX Norte"),
            ("SKU-00006", 30, "CDMX Norte"),
            ("SKU-00007", 100, "CDMX Norte"),
            ("SKU-00008", 40, "CDMX Norte"),
            ("SKU-00009", 200, "CDMX Norte"),
            ("SKU-00010", 150, "CDMX Norte"),
            # Guadalajara - más alimentos
            ("SKU-00001", 150, "Guadalajara"),
            ("SKU-00002", 120, "Guadalajara"),
            ("SKU-00003", 90, "Guadalajara"),
            ("SKU-00004", 110, "Guadalajara"),
        ]

        for sku, cantidad, almacen_nombre in existencias:
            # Buscar almacén y producto
            from sqlalchemy import select
            from src.infrastructure.persistence.models import AlmacenModel
            almacen_query = select(AlmacenModel).where(AlmacenModel.nombre == almacen_nombre)
            almacen_model = session.execute(almacen_query).scalar_one_or_none()
            if not almacen_model:
                continue

            # Crear existencia
            from src.domain.entities import ExistenciaProducto
            existencia = ExistenciaProducto(
                producto_id=uuid4(),  # Placeholder - debería ser el ID real del producto
                almacen_id=almacen_model.id,
                sku=Sku.of(sku),
                cantidad_disponible=cantidad,
            )
            existencia_model = _map_existencia_from_domain(existencia)

            # Buscar el producto real y actualizar el producto_id
            from sqlalchemy import select
            from src.infrastructure.persistence.models import ProductoModel
            producto_model = session.execute(
                select(ProductoModel).where(ProductoModel.sku == sku)
            ).scalar_one_or_none()

            if producto_model:
                existencia_model.producto_id = producto_model.id
                session.add(existencia_model)
                session.commit()
                print(f"✓ Existencia creada: {sku} en {almacen_nombre} ({cantidad} unidades)")

        # Crear clientes de ejemplo
        clientes_data = [
            ("Juan Pérez", "juan.perez@email.com", "555-1234", "Calle 1 #100, Centro, CDMX, 06600"),
            ("María López", "maria.lopez@email.com", "555-5678", "Av Reforma 500, Cuauhtémoc, CDMX, 06600"),
            ("Carlos García", "carlos.garcia@email.com", "33-1234-5678", "Av Chapultepec 123, Polanco, CDMX, 11500"),
            ("Ana Martínez", "ana.martinez@email.com", "33-8765-4321", "Calle 5 #45, Centro, Guadalajara, 44100"),
        ]

        for nombre, email, telefono, direccion_str in clientes_data:
            # Parsear dirección
            partes = direccion_str.split(", ")
            calle_num = partes[0].split(" # ")
            direccion = DireccionEntrega(
                calle=calle_num[0],
                numero=calle_num[1],
                colonia=partes[1],
                ciudad=partes[2],
                codigo_postal=partes[3],
            )

            cliente = Cliente.crear(nombre=nombre, email=email, telefono=telefono)
            cliente.agregar_direccion(direccion)

            repo_cliente = SqlAlchemyRepositorioCliente(session)
            repo_cliente.guardar(cliente)
            session.commit()
            print(f"✓ Cliente creado: {nombre}")

        print("\n✓ Datos semilla generados exitosamente!")

    except Exception as e:
        print(f"❌ Error al generar datos semilla: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_data()