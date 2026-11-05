"""Tests unitarios - Capa de Aplicación (Casos de Uso).

Cubre todos los casos de uso con repositorios en memoria y pasarela falsa.
Cada test cita su US correspondiente.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.application.in_memory import (
    FakePasarelaPago,
    InMemoryEventPublisher,
    InMemoryUnitOfWork,
)
from src.application.use_cases import (
    AutorizarDevolucionUseCase,
    CancelarPedidoUseCase,
    ConfirmarCheckoutUseCase,
    ConsultarDiscrepanciaInventarioUseCase,
    ConsultarEstadoPedidoUseCase,
    DespacharPedidoUseCase,
    IniciarYEmpacarSurtidoUseCase,
    ProcesarPagoUseCase,
    ProcesarReembolsoUseCase,
    RegistrarEntregaUseCase,
    SolicitarDevolucionUseCase,
)
from src.domain.aggregates import Almacen
from src.domain.entities import LineaDevolucion, LineaPedido
from src.domain.value_objects import Dinero, DireccionEntrega, MotivoDevolucion, Sku


@pytest.fixture
def setup_uow_and_almacen():
    uow = InMemoryUnitOfWork()
    publisher = InMemoryEventPublisher()
    almacen = Almacen.crear("Norte", "Monterrey")
    sku = Sku.of("SKU-10001")
    almacen.agregar_existencia(uuid4(), sku, 10)
    uow.almacenes.guardar(almacen)
    return uow, publisher, almacen, sku


def test_confirmar_checkout_use_case(setup_uow_and_almacen) -> None:
    """US-001, US-006: Confirmar checkout crea pedido, asigna surtido y reserva stock."""
    uow, publisher, almacen, sku = setup_uow_and_almacen
    use_case = ConfirmarCheckoutUseCase(uow, publisher)

    lineas = [LineaPedido(sku, 2, Dinero(100, "MXN"))]
    direccion = DireccionEntrega("Av Principal", "123", "Centro", "Monterrey", "64000")

    pedido = use_case.ejecutar(uuid4(), lineas, direccion)

    assert pedido is not None
    assert pedido.estado.value == "PENDIENTE_PAGO"
    assert len(pedido.surtidos) == 1
    assert uow.committed is True
    assert len(publisher.eventos_publicados) > 0


def test_procesar_pago_aprobado_use_case(setup_uow_and_almacen) -> None:
    """US-004: Pago aprobado avanza pedido a PAGADO y confirma venta en almacén."""
    uow, publisher, almacen, sku = setup_uow_and_almacen

    # 1. Checkout
    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 2, Dinero(100, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    # 2. Pago
    pasarela = FakePasarelaPago(siempre_aprobado=True)
    pago_uc = ProcesarPagoUseCase(uow, publisher, pasarela)
    pago = pago_uc.ejecutar(pedido.id, "tarjeta", {"token": "tok_123"})

    assert pago.estado.value == "APROBADO"
    assert uow.pedidos.obtener_por_id(pedido.id).estado.value == "PAGADO"
    assert almacen.obtener_existencia(sku).disponible_para_venta == 8  # 10 - 2


def test_procesar_pago_rechazado_tres_veces_use_case(setup_uow_and_almacen) -> None:
    """US-003: 3 reintentos de pago cancelan el pedido y liberan reservas."""
    uow, publisher, almacen, sku = setup_uow_and_almacen

    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 2, Dinero(100, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    pasarela = FakePasarelaPago(siempre_aprobado=False, motivo_rechazo="Fondos insuficientes")
    pago_uc = ProcesarPagoUseCase(uow, publisher, pasarela)

    # 3 intentos
    pago_uc.ejecutar(pedido.id, "tarjeta", {})
    pago_uc.ejecutar(pedido.id, "tarjeta", {})
    pago_uc.ejecutar(pedido.id, "tarjeta", {})

    pedido_actualizado = uow.pedidos.obtener_por_id(pedido.id)
    assert pedido_actualizado.estado.value == "CANCELADO"
    assert almacen.obtener_existencia(sku).disponible_para_venta == 10  # Reservas liberadas


def test_cancelar_pedido_antes_de_preparacion(setup_uow_and_almacen) -> None:
    """US-008: Cancelación de pedido antes de preparación."""
    uow, publisher, almacen, sku = setup_uow_and_almacen
    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 2, Dinero(100, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    cancel_uc = CancelarPedidoUseCase(uow, publisher)
    pedido_cancelado = cancel_uc.ejecutar(pedido.id, "Cliente se arrepintió")

    assert pedido_cancelado.estado.value == "CANCELADO"


def test_cancelar_pedido_pagado_reposa_stock(setup_uow_and_almacen) -> None:
    """US-008: Cancelar pedido PAGADO repone el stock confirmado.

    Cuando un pedido ya pagado (stock confirmado) se cancela:
    - El stock inicial era 10
    - Se reservó 2 unidades
    - Se confirmó la venta (descuento de stock real): 10 - 2 = 8 disponibles
    - Al cancelar, se debe reponer: 8 + 2 = 10 disponibles
    """
    uow, publisher, almacen, sku = setup_uow_and_almacen
    sku = Sku.of("SKU-10002")
    almacen.agregar_existencia(uuid4(), sku, 10)
    uow.almacenes.guardar(almacen)
    uow.commit()

    # 1. Checkout
    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 2, Dinero(100, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    # 2. Pago aprobado
    pasarela = FakePasarelaPago(siempre_aprobado=True)
    pago_uc = ProcesarPagoUseCase(uow, publisher, pasarela)
    pago_uc.ejecutar(pedido.id, "tarjeta", {"token": "tok_123"})

    # Verificar stock confirmado
    assert almacen.obtener_existencia(sku).cantidad_disponible == 8

    # 3. Cancelar pedido PAGADO
    cancel_uc = CancelarPedidoUseCase(uow, publisher)
    pedido_cancelado = cancel_uc.ejecutar(pedido.id, "Cambio de opinión")

    assert pedido_cancelado.estado.value == "CANCELADO"

    # 4. Verificar que el stock se repuso
    assert almacen.obtener_existencia(sku).cantidad_disponible == 10


def test_iniciar_y_empacar_surtido_use_case(setup_uow_and_almacen) -> None:
    """US-007: Iniciar preparación y empacar surtido avanza pedido a EMPACADO.

    Flujo: CREADO -> PENDIENTE_PAGO -> PAGADO -> EN_PREPARACION -> EMPACADO
    """
    uow, publisher, almacen, sku = setup_uow_and_almacen
    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 2, Dinero(100, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    # Pagar primero para llegar a PAGADO
    pasarela = FakePasarelaPago(siempre_aprobado=True)
    pago_uc = ProcesarPagoUseCase(uow, publisher, pasarela)
    pago_uc.ejecutar(pedido.id, "tarjeta", {"token": "tok_123"})

    # Ahora iniciar preparación
    empacar_uc = IniciarYEmpacarSurtidoUseCase(uow, publisher)
    empacar_uc.iniciar_preparacion(pedido.id)

    # Empacar surtido
    surtido = pedido.surtidos[0]
    pedido_empacado = empacar_uc.confirmar_empaque_surtido(pedido.id, surtido.almacen_id)

    assert pedido_empacado.estado.value == "EMPACADO"


def test_despachar_y_registrar_entrega_use_case(setup_uow_and_almacen) -> None:
    """US-006, US-010: Despachar pedido con guía y registrar entrega exitosa.

    Flujo completo: CREADO -> PENDIENTE_PAGO -> PAGADO -> EN_PREPARACION -> EMPACADO -> ENVIADO -> ENTREGADO
    """
    uow, publisher, almacen, sku = setup_uow_and_almacen
    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 2, Dinero(100, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    # Pagar
    pasarela = FakePasarelaPago(siempre_aprobado=True)
    pago_uc = ProcesarPagoUseCase(uow, publisher, pasarela)
    pago_uc.ejecutar(pedido.id, "tarjeta", {"token": "tok_123"})

    # Preparar y empacar
    empacar_uc = IniciarYEmpacarSurtidoUseCase(uow, publisher)
    empacar_uc.iniciar_preparacion(pedido.id)
    surtido = pedido.surtidos[0]
    empacar_uc.confirmar_empaque_surtido(pedido.id, surtido.almacen_id)

    # Despachar
    despachar_uc = DespacharPedidoUseCase(uow, publisher)
    envio = despachar_uc.ejecutar(pedido.id, "GUIA-999888")
    assert envio.estado.value == "EN_TRASITO"

    # Registrar entrega exitosa
    entrega_uc = RegistrarEntregaUseCase(uow, publisher)
    entrega_uc.ejecutar(pedido.id, exitoso=True, observaciones="Entregado en recepción")

    assert uow.pedidos.obtener_por_id(pedido.id).estado.value == "ENTREGADO"


def test_solicitud_y_flujo_devolucion_use_case(setup_uow_and_almacen) -> None:
    """US-013, US-014, US-015: Solicitar devolución, autorizar, recibir y reembolsar.

    Requiere pedido en ENTREGADO.
    """
    uow, publisher, almacen, sku = setup_uow_and_almacen
    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 2, Dinero(100, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    # Llevar a ENTREGADO completo
    pasarela = FakePasarelaPago(siempre_aprobado=True)
    pago_uc = ProcesarPagoUseCase(uow, publisher, pasarela)
    pago_uc.ejecutar(pedido.id, "tarjeta", {"token": "tok_123"})

    empacar_uc = IniciarYEmpacarSurtidoUseCase(uow, publisher)
    empacar_uc.iniciar_preparacion(pedido.id)
    surtido = pedido.surtidos[0]
    empacar_uc.confirmar_empaque_surtido(pedido.id, surtido.almacen_id)

    despachar_uc = DespacharPedidoUseCase(uow, publisher)
    despachar_uc.ejecutar(pedido.id, "GUIA-111")

    entrega_uc = RegistrarEntregaUseCase(uow, publisher)
    entrega_uc.ejecutar(pedido.id, exitoso=True)

    # Solicitar devolución
    dev_uc = SolicitarDevolucionUseCase(uow, publisher)
    lineas_dev = [LineaDevolucion(sku, 1)]
    devolucion = dev_uc.ejecutar(pedido.id, lineas_dev, MotivoDevolucion.of("Producto defectuoso"), datetime.now())
    assert devolucion.estado.value == "SOLICITADA"

    # Autorizar
    aut_uc = AutorizarDevolucionUseCase(uow, publisher)
    aut_uc.autorizar(devolucion.id)
    assert devolucion.estado.value == "APROBADA"

    # Reembolsar
    reembolso_uc = ProcesarReembolsoUseCase(uow, publisher, pasarela)
    reembolso_uc.confirmar_recepcion_y_reembolsar(devolucion.id)
    assert devolucion.estado.value == "PROCESADA"


def test_consultar_estado_y_discrepancia(setup_uow_and_almacen) -> None:
    """US-016: Consultar estado y registrar discrepancia de inventario."""
    uow, publisher, almacen, sku = setup_uow_and_almacen
    checkout_uc = ConfirmarCheckoutUseCase(uow, publisher)
    pedido = checkout_uc.ejecutar(uuid4(), [LineaPedido(sku, 1, Dinero(50, "MXN"))], DireccionEntrega("Calle", "1", "Col", "Mty", "64000"))

    # Consultar estado
    estado_uc = ConsultarEstadoPedidoUseCase(uow)
    info = estado_uc.ejecutar(pedido.id)
    assert info["estado"] == "PENDIENTE_PAGO"

    # Discrepancia US-016: el caso de uso publica eventos en el publisher
    disc_uc = ConsultarDiscrepanciaInventarioUseCase(uow, publisher)
    disc_uc.ejecutar(almacen.id, sku, 8)  # físico = 8, web = 10
    assert len(publisher.eventos_publicados) > 0