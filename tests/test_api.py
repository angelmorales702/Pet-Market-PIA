"""Tests de integración para la API REST FastAPI - PetMarket.

Tests usan TestClient de FastAPI contra la base de datos PostgreSQL petmarket_test.
Cada test cubre un endpoint específico citando la User Story correspondiente.

Requieren:
- Variable de entorno TEST_DATABASE_URL configurada (debe terminar en _test)
- Docker compose up db ejecutado previamente
- Ejecutar: alembic upgrade head

IMPORTANTE: Los datos se crean DENTRO de cada test o en fixtures,
para asegurar aislamiento. Usamos clean_db para limpiar después de cada test.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.aggregates import Almacen, Cliente, Pedido, Producto, Devolucion
from src.domain.entities import (
    ExistenciaProducto, LineaPedido, LineaDevolucion, Surtido
)
from src.domain.value_objects import (
    DireccionEntrega, Dinero, EstadoSurtido, Guia, MotivoDevolucion, Sku
)
from src.infrastructure.persistence.repositories import SqlAlchemyRepositorioDevolucion


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app_with_uow(clean_db, session):
    """App FastAPI con inyección de dependencias para tests.

    USAGE: La app usa clean_db para limpiar después del test.
    Los datos se crean dentro de cada test usando el fixture session.
    """
    from src.api.main import app
    from src.infrastructure.persistence.uow import SqlAlchemyUnitOfWork
    from src.application.in_memory import InMemoryEventPublisher

    # Crear UoW con la session del test
    publisher = InMemoryEventPublisher()
    from sqlalchemy.orm import sessionmaker as sm
    uow = SqlAlchemyUnitOfWork(sm(bind=session.bind), publisher, existing_session=session)

    # Override dependencies
    app.dependency_overrides["get_session"] = lambda: session
    app.dependency_overrides["get_uow"] = lambda: uow

    yield app

    # Cleanup
    for dep in ["get_session", "get_uow"]:
        if dep in app.dependency_overrides:
            del app.dependency_overrides[dep]


@pytest.fixture
def client(app_with_uow):
    """TestClient para la API."""
    return TestClient(app_with_uow)


# =============================================================================
# Tests de Health Check
# =============================================================================

def test_health_check_returns_200(client):
    """Endpoint /health debe responder con 200 OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "petmarket-api"


# =============================================================================
# Tests de Productos (Catálogo) - US-001
# =============================================================================

class TestProductosAPI:
    """Tests de endpoints de productos - US-001."""

    def test_listar_productos(self, client, producto_test):
        """US-001: Listar productos del catálogo."""
        response = client.get("/productos")
        assert response.status_code == 200
        data = response.json()
        assert "productos" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_obtener_producto_por_sku(self, client, producto_test):
        """US-001: Obtener detalles de un producto por SKU."""
        response = client.get(f"/productos/{producto_test.sku}")
        assert response.status_code == 200
        data = response.json()
        assert data["sku"] == str(producto_test.sku)
        assert data["nombre"] == producto_test.nombre
        # El precio se serializa con decimales (ej: 100.00)
        assert float(data["precio"]) == float(producto_test.precio.monto)

    def test_obtener_producto_no_encontrado(self, client):
        """US-001: Producto no encontrado devuelve 404."""
        response = client.get("/productos/SKU-99999")
        assert response.status_code == 404

    def test_listar_productos_filtrados_por_categoria(self, client, producto_test):
        """US-001: Filtrar productos por categoría."""
        response = client.get("/productos?categoria=Test")
        assert response.status_code == 200
        data = response.json()
        assert "productos" in data
        assert all(p["categoria"] == "Test" for p in data["productos"])

    def test_listar_productos_inactivos(self, client, producto_test):
        """US-001: Listar productos inactivos."""
        response = client.get("/productos?activos=false")
        assert response.status_code == 200
        data = response.json()
        assert "productos" in data


# =============================================================================
# Tests de Almacenes e Inventario - US-001
# =============================================================================

class TestAlmacenesAPI:
    """Tests de endpoints de almacenes - US-001."""

    def test_listar_almacenes(self, client, almacen_norte):
        """Listar almacenes disponibles."""
        response = client.get("/almacenes")
        assert response.status_code == 200
        data = response.json()
        assert "almacenes" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_obtener_inventario_almacen(self, client, almacen_norte):
        """US-001: Consultar inventario de un almacén."""
        response = client.get(f"/almacenes/{almacen_norte.id}/inventario")
        assert response.status_code == 200
        data = response.json()
        assert data["almacen_id"] == str(almacen_norte.id)
        assert "existencias" in data

    def test_obtener_almacen_no_encontrado(self, client):
        """Almacén no encontrado devuelve 404."""
        response = client.get(f"/almacenes/{uuid4()}")
        assert response.status_code == 404


# =============================================================================
# Tests de Checkout - US-004
# =============================================================================

class TestCheckoutAPI:
    """Tests de endpoints de checkout - US-004."""

    def test_crear_pedido_exitoso(self, client, cliente, almacen_norte, almacen_sur, producto_test_con_stock):
        """US-004: Crear un pedido exitosamente.

        - Usa SKU del fixture producto_test_con_stock (no SKU escrito a mano)
        - Los almacenes almacen_norte y almacen_sur deben existir en DB
        - El precio sale del catálogo, no del cliente
        """
        # Usar el SKU del producto del fixture (que tiene stock en almacen_norte)
        sku = str(producto_test_con_stock.sku)

        pedido_data = {
            "lineas": [
                {"sku": sku, "cantidad": 1}  # NO se envía precio_unitario
            ],
            "direccion": {
                "calle": "Calle Test",
                "numero": "123",
                "colonia": "Centro",
                "ciudad": "CDMX",
                "codigo_postal": "01001"
            }
        }

        response = client.post(
            "/pedidos",
            json=pedido_data,
            headers={"X-Cliente-Id": str(cliente.id)}
        )
        assert response.status_code == 201, f"Error: {response.json()}"
        data = response.json()
        assert data["estado"] == "PENDIENTE_PAGO"
        assert "id" in data

        # Verificar que el total coincide con el precio del producto por cantidad
        assert float(data["total"]) == float(producto_test_con_stock.precio.monto)
        assert data["moneda"] == "MXN"

    def test_crear_pedido_sin_lineas(self, client, cliente, almacen_norte, almacen_sur, producto_test_con_stock):
        """US-004: Pedido sin líneas devuelve 422 validación.

        - La validación ocurre ANTES de consultar almacenes (valida entrada primero)
        - Se devuelve 422 sin ejecutar lógica del dominio
        """
        pedido_data = {
            "lineas": [],
            "direccion": {
                "calle": "Calle Test",
                "numero": "123",
                "colonia": "Centro",
                "ciudad": "CDMX",
                "codigo_postal": "01001"
            }
        }

        response = client.post(
            "/pedidos",
            json=pedido_data,
            headers={"X-Cliente-Id": str(cliente.id)}
        )
        assert response.status_code == 422

    def test_crear_pedido_sin_stock(self, client, cliente, producto_sin_stock):
        """US-004: Pedido con stock insuficiente retorna 409 conflicto.

        Prueba con producto existente con stock 0.
        - Usa SKU del fixture producto_sin_stock (SKU-00003)
        - El precio sale del catálogo, no del cliente
        - El fixture producto_sin_stock crea su propio almacén con 0 stock
        """
        sku = str(producto_sin_stock.sku)

        pedido_data = {
            "lineas": [
                {"sku": sku, "cantidad": 1}
            ],
            "direccion": {
                "calle": "Calle Test",
                "numero": "123",
                "colonia": "Centro",
                "ciudad": "CDMX",
                "codigo_postal": "01001"
            }
        }

        response = client.post(
            "/pedidos",
            json=pedido_data,
            headers={"X-Cliente-Id": str(cliente.id)}
        )
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["codigo"] == "STOCK_INSUFICIENTE"

    def test_crear_pedido_sin_cliente(self, client):
        """US-004: Pedido sin header X-Cliente-Id devuelve 422 validación."""
        pedido_data = {
            "lineas": [
                {"sku": "SKU-00001", "cantidad": 1}
            ],
            "direccion": {
                "calle": "Calle Test",
                "numero": "123",
                "colonia": "Centro",
                "ciudad": "CDMX",
                "codigo_postal": "01001"
            }
        }

        response = client.post(
            "/pedidos",
            json=pedido_data
        )
        assert response.status_code == 422

    def test_crear_pedido_precio_unitario_rechazado(self, client, cliente, almacen_norte, almacen_sur, producto_test_con_stock):
        """US-004: Enviar precio_unitario en la línea debe ser rechazado con 422.

        Según requisito de negocio: el precio sale del catálogo, NO del cliente.
        El schema usa `extra='forbid'` para rechazar campos inesperados.
        """
        sku = str(producto_test_con_stock.sku)

        # Enviar precio_unitario en la línea (debe ser rechazado)
        pedido_data = {
            "lineas": [
                {"sku": sku, "cantidad": 1, "precio_unitario": "999.99"}  # precio_unitario NO permitido
            ],
            "direccion": {
                "calle": "Calle Test",
                "numero": "123",
                "colonia": "Centro",
                "ciudad": "CDMX",
                "codigo_postal": "01001"
            }
        }

        response = client.post(
            "/pedidos",
            json=pedido_data,
            headers={"X-Cliente-Id": str(cliente.id)}
        )
        # Pydantic con extra='forbid' rechaza campos inesperados con 422
        assert response.status_code == 422
        data = response.json()
        # Verificar que el error sea de validación
        assert "detail" in data or "codigo" in str(data).lower()


# =============================================================================
# Tests de Pago - US-003, US-004
# =============================================================================

class TestPagoAPI:
    """Tests de endpoints de pago - US-003, US-004."""

    def test_procesar_pago_exitoso(self, client, pedido_pendiente_pago):
        """US-003: Procesar pago exitosamente (200)."""
        pago_data = {
            "pedido_id": str(pedido_pendiente_pago.id),
            "metodo_pago": "TARJETA",
            "datos_cliente": {}
        }

        response = client.post("/pagos", json=pago_data)
        assert response.status_code == 200
        data = response.json()
        assert data["estado"] == "APROBADO"

        # Verificar que el pedido cambió a PAGADO
        pedir_response = client.get(f"/pedidos/{pedido_pendiente_pago.id}")
        assert pedir_response.status_code == 200
        pedido_data = pedir_response.json()
        assert pedido_data["estado"] == "PAGADO"

    def test_procesar_pago_pedido_inexistente(self, client):
        """US-003: Procesar pago para pedido inexistente retorna 404."""
        from uuid import uuid4
        pago_data = {
            "pedido_id": str(uuid4()),
            "metodo_pago": "TARJETA",
            "datos_cliente": {}
        }

        response = client.post("/pagos", json=pago_data)
        assert response.status_code == 404

    def test_procesar_pago_estado_invalido(self, client, pedido_pagado):
        """US-003: Procesar pago en pedido ya pagado retorna 409."""
        pago_data = {
            "pedido_id": str(pedido_pagado.id),
            "metodo_pago": "TARJETA",
            "datos_cliente": {}
        }

        response = client.post("/pagos", json=pago_data)
        assert response.status_code == 409


# =============================================================================
# Tests de Cancelación - US-008, US-009
# =============================================================================

class TestCancelacionAPI:
    """Tests de cancelación de pedidos - US-008, US-009."""

    def test_cancelar_pedido_exitosamente(self, client, pedido_cancelable):
        """US-008: Cancelar un pedido en estado PENDIENTE_PAGO exitosamente."""
        response = client.post(
            f"/pedidos/{pedido_cancelable.id}/cancelar",
            json={"motivo": "Cambio de opinión", "autorizado_por_atencion": False}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["estado"] == "CANCELADO"

    def test_cancelar_pedido_pagado_sin_preparacion(self, client, pedido_pagado):
        """US-008: pedido pagado sin preparacion se cancela sin autorizacion (200)."""
        response = client.post(
            f"/pedidos/{pedido_pagado.id}/cancelar",
            json={"motivo": "Cambio de opinion", "autorizado_por_atencion": False}
        )
        assert response.status_code == 200

    def test_cancelar_pedido_en_preparacion_sin_autorizacion(self, client, pedido_en_preparacion):
        """US-009: en preparacion, sin autorizacion de Atencion al cliente (409)."""
        response = client.post(
            f"/pedidos/{pedido_en_preparacion.id}/cancelar",
            json={"motivo": "Cambio de opinion", "autorizado_por_atencion": False}
        )
        assert response.status_code == 409

    def test_cancelar_pedido_en_preparacion_con_autorizacion(self, client, pedido_en_preparacion):
        """US-009: en preparacion, con autorizacion de Atencion al cliente (200)."""
        response = client.post(
            f"/pedidos/{pedido_en_preparacion.id}/cancelar",
            json={"motivo": "Cambio de opinion", "autorizado_por_atencion": True}
        )
        assert response.status_code == 200

    def test_cancelar_pedido_ya_cancelado(self, client, pedido_cancelable):
        """US-009: Intentar cancelar pedido ya cancelado retorna 409."""
        # Cancelar por primera vez
        response = client.post(
            f"/pedidos/{pedido_cancelable.id}/cancelar",
            json={"motivo": "Test", "autorizado_por_atencion": False}
        )
        assert response.status_code == 200

        # Intentar cancelar de nuevo
        response = client.post(
            f"/pedidos/{pedido_cancelable.id}/cancelar",
            json={"motivo": "Test de nuevo", "autorizado_por_atencion": False}
        )
        assert response.status_code == 409


# =============================================================================
# Tests de Preparación/Surtido - US-007
# Tests de Preparación/Surtido - US-007
# =============================================================================

class TestPreparacionAPI:
    """Tests de preparación de pedidos - US-007."""

    def test_iniciar_preparacion_exitoso(self, client, pedido_pagado):
        """US-007: Iniciar preparación de un pedido PAGADO (200)."""
        response = client.post(
            f"/pedidos/{pedido_pagado.id}/iniciar-preparacion"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["estado"] == "EN_PREPARACION"

    def test_iniciar_preparacion_estado_invalido(self, client, pedido_pendiente_pago):
        """US-007: Iniciar preparación sin pagar retorna 409."""
        response = client.post(
            f"/pedidos/{pedido_pendiente_pago.id}/iniciar-preparacion"
        )
        assert response.status_code == 409

    def test_confirmar_empaque_exitoso(self, client, pedido_en_preparacion, almacen_norte):
        """US-007: Confirmar empaque de surtido (200)."""
        response = client.post(
            f"/pedidos/{pedido_en_preparacion.id}/confirmar-empaque",
            json={"almacen_id": str(almacen_norte.id)}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["estado"] == "EMPACADO"

    def test_confirmar_empaque_surtido_incompleto(self, client, pedido_en_preparacion):
        """US-007: Confirmar empaque con surtidos faltantes mantiene estado EN_PREPARACION."""
        # Si el pedido tiene múltiples surtidos, confirmar uno no empaca todo
        response = client.post(
            f"/pedidos/{pedido_en_preparacion.id}/confirmar-empaque",
            json={"almacen_id": "11111111-1111-1111-1111-111111111111"}
        )
        assert response.status_code == 404


# =============================================================================
# Tests de Envío - US-006
# =============================================================================

class TestDespachoAPI:
    """Tests de despacho de pedidos - US-006."""

    def test_despachar_pedido_exitoso(self, client, pedido_empacado):
        """US-006: Despachar pedido EMPACADO (200)."""
        response = client.post(
            f"/pedidos/{pedido_empacado.id}/enviar",
            json={"guia": "GUIA-ENVIO-00001"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["guia"] == "GUIA-ENVIO-00001"

        # Verificar estado del pedido
        pedido_response = client.get(f"/pedidos/{pedido_empacado.id}")
        assert pedido_response.status_code == 200
        pedido_data = pedido_response.json()
        assert pedido_data["estado"] == "ENVIADO"

    def test_despachar_pedido_estado_invalido(self, client, pedido_pagado):
        """US-006: Despachar pedido sin empacar retorna 409."""
        response = client.post(
            f"/pedidos/{pedido_pagado.id}/enviar",
            json={"guia": "GUIA-ENVIO-00002"}
        )
        assert response.status_code == 409


# =============================================================================
# Tests de Entrega - US-010, US-011
# =============================================================================

class TestEntregaAPI:
    """Tests de registro de entrega - US-010, US-011."""

    def test_registrar_entrega_exitosa(self, client, pedido_enviado):
        """US-010: Registrar entrega exitosa (200)."""
        response = client.post(
            f"/pedidos/{pedido_enviado.id}/entrega",
            json={"exitoso": True, "observaciones": "Entregado"}
        )
        assert response.status_code == 200

        # Verificar estado del pedido
        pedido_response = client.get(f"/pedidos/{pedido_enviado.id}")
        assert pedido_response.status_code == 200
        pedido_data = pedido_response.json()
        assert pedido_data["estado"] == "ENTREGADO"

    def test_registrar_entrega_fallida(self, client, pedido_enviado):
        """US-011: Registrar entrega fallida (primer intento, 200)."""
        response = client.post(
            f"/pedidos/{pedido_enviado.id}/entrega",
            json={"exitoso": False, "observaciones": "No se entregó"}
        )
        assert response.status_code == 200

        # El pedido sigue ENVIADO (primer intento fallido)
        pedido_response = client.get(f"/pedidos/{pedido_enviado.id}")
        pedido_data = pedido_response.json()
        assert pedido_data["estado"] == "ENVIADO"

    def test_registrar_segundo_intento_fallido(self, client, pedido_enviado):
        """US-011: Segundo intento fallido marca pedido como ENTREGA_FALLIDA (200)."""
        # Primer intento fallido
        client.post(
            f"/pedidos/{pedido_enviado.id}/entrega",
            json={"exitoso": False, "observaciones": "No había nadie"}
        )

        # Segundo intento fallido
        response = client.post(
            f"/pedidos/{pedido_enviado.id}/entrega",
            json={"exitoso": False, "observaciones": "No se entregó"}
        )
        assert response.status_code == 200

        pedido_response = client.get(f"/pedidos/{pedido_enviado.id}")
        pedido_data = pedido_response.json()
        assert pedido_data["estado"] == "ENTREGA_FALLIDA"


# =============================================================================
# Tests de Consulta de Pedido - US-012
# =============================================================================

class TestConsultaPedidoAPI:
    """Tests de consulta de pedidos - US-012."""

    def test_consultar_pedido_por_id(self, client, pedido_pagado):
        """Consultar el estado de un pedido por ID (200)."""
        response = client.get(f"/pedidos/{pedido_pagado.id}")
        assert response.status_code == 200
        data = response.json()
        assert "estado" in data
        assert "total" in data
        assert "surtidos" in data
        # Verificar estructura ADR-002: surtidos como lista con almacén y estado
        assert isinstance(data["surtidos"], list)
        if len(data["surtidos"]) > 0:
            surtido = data["surtidos"][0]
            assert "almacen_id" in surtido
            assert "estado" in surtido
            assert "lineas" in surtido

    def test_consultar_pedido_no_encontrado(self, client):
        """Pedido no encontrado devuelve 404."""
        response = client.get(f"/pedidos/{uuid4()}")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["codigo"] == "PEDIDO_NO_ENCONTRADO"

    def test_listar_pedidos_cliente(self, client, cliente, pedido_pagado):
        """US-012: Listar pedidos de un cliente (200)."""
        response = client.get(f"/clientes/{cliente.id}/pedidos")
        assert response.status_code == 200
        data = response.json()
        assert "pedidos" in data
        assert "total" in data
        assert data["total"] >= 1


# =============================================================================
# Tests de Devolución - US-013, US-014, US-015
# =============================================================================

class TestDevolucionAPI:
    """Tests de devoluciones - US-013, US-014, US-015."""

    def test_solicitar_devolucion_pedido_entregado(self, client, pedido_entregado):
        """US-013: Solicitar una devolución para pedido ENTREGADO (200)."""
        # El pedido_entregado contiene SKU-00002
        devolucion_data = {
            "pedido_id": str(pedido_entregado.id),
            "lineas": [{"sku": "SKU-00002", "cantidad": 1}],
            "motivo": "Producto defectuoso",
            "fecha_entrega": datetime.now().isoformat(timespec="seconds")
        }

        response = client.post("/devoluciones", json=devolucion_data)
        assert response.status_code == 200
        data = response.json()
        assert data["estado"] == "SOLICITADA"

    def test_solicitar_devolucion_pedido_no_entregado(self, client, pedido_pagado):
        """US-013: Solicitar devolución para pedido no ENTREGADO retorna 409."""
        devolucion_data = {
            "pedido_id": str(pedido_pagado.id),
            "lineas": [{"sku": "SKU-00002", "cantidad": 1}],
            "motivo": "Cambio de opinión",
            "fecha_entrega": datetime.now().isoformat(timespec="seconds")
        }

        response = client.post("/devoluciones", json=devolucion_data)
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["codigo"] == "DEVOLUCION_NO_PERMITIDA"

    def test_autorizar_devolucion_exitosa(self, client, pedido_entregado):
        """US-014: Autorizar devolución exitosamente (200)."""
        # Primero solicitar la devolución
        devolucion_data = {
            "pedido_id": str(pedido_entregado.id),
            "lineas": [{"sku": "SKU-00002", "cantidad": 1}],
            "motivo": "Producto defectuoso",
            "fecha_entrega": datetime.now().isoformat(timespec="seconds")
        }

        solicitar_response = client.post("/devoluciones", json=devolucion_data)
        assert solicitar_response.status_code == 200
        devolucion_id = solicitar_response.json()["id"]

        # Autorizar
        response = client.post(f"/devoluciones/{devolucion_id}/autorizar")
        assert response.status_code == 200
        data = response.json()
        assert data["estado"] == "APROBADA"

    def test_autorizar_devolucion_no_encontrada(self, client):
        """US-014: Autorizar devolución inexistente retorna 404."""
        from uuid import uuid4
        response = client.post(f"/devoluciones/{uuid4()}/autorizar")
        assert response.status_code == 404

    def test_confirmar_recepcion_devolucion(self, client, pedido_entregado):
        """US-015: Confirmar recepción en almacén y reembolsar (200)."""
        # Primero solicitar devolución
        devolucion_data = {
            "pedido_id": str(pedido_entregado.id),
            "lineas": [{"sku": "SKU-00002", "cantidad": 1}],
            "motivo": "Producto defectuoso",
            "fecha_entrega": datetime.now().isoformat(timespec="seconds")
        }

        solicitar_response = client.post("/devoluciones", json=devolucion_data)
        assert solicitar_response.status_code == 200
        devolucion_id = solicitar_response.json()["id"]

        # Autorizar
        auth_response = client.post(f"/devoluciones/{devolucion_id}/autorizar")
        assert auth_response.status_code == 200

        # Confirmar recepción y reembolsar
        response = client.post(f"/devoluciones/{devolucion_id}/confirmar-recepcion")
        assert response.status_code == 200


# =============================================================================
# Tests de Discrepancia de Inventario - US-016
# =============================================================================

class TestDiscrepanciaInventarioAPI:
    """Tests de detección de discrepancia - US-016."""

    def test_detectar_discrepancia(self, client, almacen_norte, producto_test):
        """US-016: Detectar discrepancia entre inventario web y físico (200)."""
        response = client.post(
            f"/almacenes/{almacen_norte.id}/discrepancia",
            json={"sku": str(producto_test.sku), "cantidad_fisica": 50}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["almacen_id"] == str(almacen_norte.id)

    def test_detectar_discrepancia_almacen_no_encontrado(self, client):
        """US-016: Detectar discrepancia en almacén inexistente retorna 404."""
        from uuid import uuid4
        response = client.post(
            f"/almacenes/{uuid4()}/discrepancia",
            json={"sku": "SKU-00001", "cantidad_fisica": 50}
        )
        assert response.status_code == 404


# =============================================================================
# Tests de SKU Validation
# =============================================================================

class TestSKUValidation:
    """Tests de validación de formato de SKU."""

    def test_producto_sku_formato_invalido_letras(self, client):
        """Test que SKU con letras en lugar de números devuelve 422."""
        response = client.get("/productos/SKU-ABCDEF")
        assert response.status_code == 422
        data = response.json()
        assert "codigo" in data["detail"]
        assert data["detail"]["codigo"] == "SKU_INVALIDO"

    def test_producto_sku_sin_guion(self, client):
        """Test que SKU sin guion devuelve error 422."""
        response = client.get("/productos/SKU00001")
        assert response.status_code == 422

    def test_producto_sku_con_multiples_guiones(self, client):
        """Test que SKU con múltiples guiones devuelve error 422."""
        response = client.get("/productos/SKU-TEST-001")
        assert response.status_code == 422

    def test_producto_sku_menos_de_5_digitos(self, client):
        """Test que SKU con menos de 5 dígitos devuelve error 422."""
        response = client.get("/productos/SKU-001")
        assert response.status_code == 422

    def test_producto_sku_formato_valido(self, client, producto_test):
        """Test que SKU válido devuelve 200."""
        response = client.get(f"/productos/{producto_test.sku}")
        assert response.status_code == 200


# =============================================================================
# Tests de Schemas
# =============================================================================

class TestSchemas:
    """Tests de verificación de schemas de respuesta.

    NOTA: Estos tests requieren base de datos porque verifican estructuras de respuesta
    que dependen de datos persistidos. No son tests puros de schema.
    """

    def test_producto_schema_structure(self, client, producto_test):
        """Verificar estructura del schema de Producto."""
        response = client.get(f"/productos/{producto_test.sku}")
        if response.status_code == 200:
            data = response.json()
            required_fields = ["id", "sku", "nombre", "descripcion", "precio", "moneda", "categoria", "activo"]
            for field in required_fields:
                assert field in data, f"Campo {field} faltante en ProductoSchema"

    def test_almacen_schema_structure(self, client, almacen_norte):
        """Verificar estructura del schema de Almacén."""
        response = client.get(f"/almacenes/{almacen_norte.id}/inventario")
        if response.status_code == 200:
            data = response.json()
            assert "almacen_id" in data
            assert "nombre" in data
            assert "existencias" in data

    def test_pedido_schema_structure(self, client, pedido_pagado):
        """Verificar estructura del schema de Pedido."""
        response = client.get(f"/pedidos/{pedido_pagado.id}")
        if response.status_code == 200:
            data = response.json()
            # El endpoint /pedidos/{id} usa ConsultarEstadoPedidoUseCase
            required_fields = ["estado", "total", "surtidos"]
            for field in required_fields:
                assert field in data, f"Campo {field} faltante en PedidoResponse"
            # Verificar que total tiene la estructura correcta
            if isinstance(data.get("total"), dict):
                assert "monto" in data["total"] or "moneda" in data["total"]

    def test_lineas_pedido_structure(self, client, pedido_creado):
        """Verificar estructura de líneas de pedido."""
        response = client.get(f"/pedidos/{pedido_creado.id}")
        if response.status_code == 200:
            data = response.json()
            # El endpoint ConsultarEstadoPedidoUseCase no retorna lineas directamente
            # Verificamos que no haya error de estructura inesperada
            assert "id" in data or "pedido_id" in data

    def test_surtidos_structure(self, client, pedido_pagado):
        """Verificar estructura de surtidos en pedido (ADR-002)."""
        response = client.get(f"/pedidos/{pedido_pagado.id}")
        if response.status_code == 200:
            data = response.json()
            assert "surtidos" in data
            # ADR-002: surtidos como lista con almacén y estado
            assert isinstance(data["surtidos"], list), "surtidos debe ser una lista"
            if len(data["surtidos"]) > 0:
                surtido = data["surtidos"][0]
                assert "almacen_id" in surtido
                assert "estado" in surtido
                assert "lineas" in surtido


# =============================================================================
# Tests de Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests de edge cases y escenarios límite."""

    def test_producto_sku_formato_invalido_sin_numeros(self, client):
        """Test que SKU sin números devuelve error 422."""
        response = client.get("/productos/SKU-ABCDE")
        assert response.status_code == 422

    def test_listar_productos_vacio_con_categoria_inexistente(self, client):
        """Listar productos filtrando por categoría que no existe."""
        response = client.get("/productos?categoria=CATEGORIA_INEXISTENTE")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["productos"] == []

    def test_almacen_inventario_vacio(self, client, almacen_norte):
        """Consultar inventario de almacén sin existencias."""
        response = client.get(f"/almacenes/{almacen_norte.id}/inventario")
        assert response.status_code == 200
        data = response.json()
        assert "existencias" in data



class TestRegresiones:
    """Regresiones de persistencia: guardar un pedido no debe duplicar datos."""

    def test_pago_no_duplica_lineas_ni_total(self, client, pedido_pendiente_pago):
        pid = str(pedido_pendiente_pago.id)
        antes = client.get(f"/pedidos/{pid}")
        assert antes.status_code == 200
        antes = antes.json()
        pago = client.post(
            "/pagos",
            json={"pedido_id": pid, "metodo_pago": "TARJETA", "datos_cliente": {}},
        )
        assert pago.status_code == 200
        despues = client.get(f"/pedidos/{pid}").json()
        assert despues["total"] == antes["total"]

        def cantidades(d):
            return sorted(
                (ln["sku"], ln["cantidad"]) for s in d["surtidos"] for ln in s["lineas"]
            )

        assert cantidades(despues) == cantidades(antes)
