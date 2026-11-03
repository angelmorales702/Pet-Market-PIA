# Registro de Supuestos Arquitectónicos - PetMarket

Este archivo documenta los supuestos tomados cuando existe ambigüedad en los documentos fuente o discrepancias entre ellos. Cada supuesto se marca con `# SUPUESTO: validar con el negocio` en el código y TRAZABILIDAD.md.

---

## 1. Creación del Pedido: ¿Antes o después del pago?
- **BRD / US-004:** El pedido se crea en estado `CREADO` al iniciar checkout, pasa a `PENDIENTE_PAGO` tras asignación de almacenes (surtidos), y a `PAGADO` tras confirmación de pago.
- **Implementación actual:** `Pedido.crear()` → `CREADO`; `asignar_surtidos()` → `PENDIENTE_PAGO`; `marcar_pagado()` → `PAGADO`.
- **# SUPUESTO: validar con el negocio** — Confirmar si el pedido debe persistirse antes de pago o solo tras aprobación.

---

## 2. Reintentos de Pago (3 reintentos = cancela al 4.º rechazo)
- **US-003 / BRD:** "Máximo 3 reintentos". En la 3.ª rechazo, el pedido se cancela automáticamente.
- **Implementación:** `Pedido.marcar_pago_rechazado()` incrementa contador; al llegar a 3 llama a `cancelar()`.
- **# SUPUESTO: validar con el negocio** — ¿El contador es por sesión de checkout o por pedido? ¿Se permite reiniciar checkout tras cancelación?

---

## 3. Producto Agotado: Quitar solo la línea y reembolsar
- **US-005 / BRD:** Si durante la asignación no hay stock en **ningún** almacén, se omite esa línea y se emite `StockInsuficienteEvent`.
- **Implementación:** `AsignacionAlmacenService.asignar()` emite evento y continua con las líneas que sí tienen stock.
- **# SUPUESTO: validar con el negocio** — ¿El cliente es notificado y decide si continúa? ¿El reembolso es inmediato o al cierre del pedido?

---

## 4. Cancelación Tardía con Autorización de Atención al Cliente
- **US-009 / BRD:** "Cancelación después de que el pedido haya entrado en preparación requiere autorización de Atención al cliente".
- **Implementación actual:** `state_machine.py` bloquea cancelación en `ENVIADO`, `ENTREGADO`, `ENTREGA_FALLIDA` con `CancelacionNoPermitidaError`. `EN_PREPARACION` y `EMPACADO` **sí permiten cancelar** (guard solo bloquea desde ENVIADO).
- **# SUPUESTO: validar con el negocio** — Definir exactamente desde qué estado requiere autorización explícita y modelar el flujo de "autorización" (servicio de dominio, proceso humano, etc.).

---

## 5. Pedido pasa a Enviado/Entregado con dos Envíos (Surtidos)
- **US-006 / BRD / ADR-002:** Un pedido puede tener múltiples surtidos (uno por almacén). Cada surtido genera su propio `Envio` con `Guia`. El pedido avanza a `ENVIADO` cuando **todos** los surtidos están empacados y despachados.
- **Implementación:** `Pedido.confirmar_empaque()` verifica `all(s.estado == EMPACADO)` antes de `EMPACADO` → `ENVIADO`. `marcar_enviado()` recibe una guía (en la práctica, una por surtido).
- **# SUPUESTO: validar con el negocio** — Cómo se representa "Enviado" cuando hay múltiples guías. Costo de envío prorrateado (ver TRAZABILIDAD.md).

---

## 6. Estado "Cerrado"
- **BRD / Diagrama_de_clases.md:** No aparece explícitamente `CERRADO` en el estado del Pedido. Estados finales: `ENTREGADO`, `CANCELADO`, `DEVUELTO`, `ENTREGA_FALLIDA`.
- **Implementación:** No existe `EstadoPedido.CERRADO`. Se considera "cerrado" implícitamente al llegar a estados terminales.
- **# SUPUESTO: validar con el negocio** — ¿Se necesita estado explícito `CERRADO` para reportes / auditoría?

---

## 7. Días Hábiles (Lunes a Viernes, sin festivos)
- **US-013 / BRD:** "5 días hábiles posteriores a la entrega" para devoluciones.
- **Implementación:** `CalendarioDiasHabilesBasico` cuenta Lun-Vie, permite agregar festivos opcionales.
- **# SUPUESTO: validar con el negocio** — Lista de festivos oficiales, zona horaria.

---

## 8. Reserva de 15 Minutos (Reloj Inyectable)
- **US-002 / BRD:** "Reserva de stock por 15 minutos durante checkout".
- **Implementación:** Interfaz `Reloj` + `RelojSistema` / `RelojFijo` para tests. `ReservaExpiradaService` con `minutos_reserva=15`.
- **# SUPUESTO: validar con el negocio** — ¿La reserva se extiende si el usuario está activo en checkout? ¿Qué pasa si paga en minuto 14:59?

---

## 9. Indicador de Discrepancia de Inventario (US-016) — **IMPLEMENTADO**
- **BRD / US-016:** "Generación del indicador de discrepancia comparando inventario web vs físico".
- **Implementación:** `Almacen.detectar_discrepancia(sku, cantidad_fisica)` → emite `DiscrepanciaInventarioDetectadaEvent`. Specification `DiscrepanciaInventarioSpec`. Tests en `test_domain_discrepancia.py` y `test_domain_services.py`.

---

## 10. Costo de Envío Prorrateado
- **US-006 / TRAZABILIDAD.md:** "Un único costo de envío prorrateado".
- **# SUPUESTO: validar con el negocio** — Fórmula de prorrateo (por peso, volumen, valor, líneas).

---

## 11. Estado REEMBOLSADO en Pago
- **Pago.reembolsar()** reutiliza `EstadoPago.RECHAZADO`.
- **# SUPUESTO: validar con el negocio** — Añadir `EstadoPago.REEMBOLSADO` explícito.

---

## 12. Motivo de Rechazo de Devolución
- **Devolucion.rechazar(motivo)** no persiste el motivo.
- **# SUPUESTO: validar con el negocio** — Guardar motivo en la entidad o evento.

---

## 13. Reprogramación de Entrega Fallida (US-012)
- **BRD / US-012:** "Reprogramación o reembolso tras entrega fallida".
- **Implementación:** Pendiente. `Pedido.marcar_entrega_fallida()` existe pero no hay flujo de reprogramación.
- **# SUPUESTO: validar con el negocio** — ¿Quién reprograma? ¿Nuevo `Envio`? ¿Cambia dirección?

---

## 14. Test de Rechazo de Devolución (US-014)
- **TRAZABILIDAD.md:** "Pendiente: test de rechazo de devolución".
- **# SUPUESTO: validar con el negocio** — Comportamiento esperado al rechazar.

---

*Última actualización: 2026-11-02 — Alineado con fuentes y código actual.*
