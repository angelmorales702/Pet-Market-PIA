# PetMarket · Diagramas UML

## Diagrama de clases

```mermaid
classDiagram
direction LR

class PedidoAppService {
  +confirmarCheckout(cmd)
  +cancelarPedido(pedidoId, motivo)
  +consultarEstado(pedidoId)
}
class PagoAppService {
  +procesarPago(pedidoId, metodoPago)
}
class PreparacionAppService {
  +iniciarPreparacion(pedidoId)
  +confirmarEmpaque(pedidoId, almacenId)
}
class EnvioAppService {
  +despacharEnvio(pedidoId)
  +registrarEntrega(envioId)
  +registrarEntregaFallida(envioId, motivo)
}
class DevolucionAppService {
  +solicitarDevolucion(pedidoId, motivo)
}

class Pedido {
  <<Aggregate Root>>
  -id
  -clienteId
  -estado : EstadoPedido
  -modalidadEntrega
  +crear(lineas, direccion, modalidad)
  +asignarSurtidos(asignacion)
  +marcarPagado()
  +marcarPagoRechazado()
  +cancelar(motivo)
  +confirmarEmpaque(almacenId)
  +marcarEnviado()
  +marcarEntregado()
  +marcarEntregaFallida()
  +total() Dinero
}
class LineaPedido {
  <<Entity>>
  -sku
  -cantidad
  -precioUnitario : Dinero
}
class Surtido {
  <<Entity>>
  -almacenId
  -empacado : bool
  +empacar()
}
class Dinero {
  <<Value Object>>
  -monto
  -moneda
}
class DireccionEntrega {
  <<Value Object>>
}
class EstadoPedido {
  <<enumeration>>
  Creado
  PendientePago
  Pagado
  EnPreparacion
  Empacado
  Enviado
  Entregado
  Cancelado
  EntregaFallida
  Devuelto
}

class Almacen {
  <<Aggregate Root>>
  -id
  +reservar(sku, cantidad)
  +liberar(sku, cantidad)
  +descontar(sku, cantidad)
  +reponer(sku, cantidad)
}
class ExistenciaProducto {
  <<Entity>>
  -sku
  -disponible
  -reservado
}
class Pago {
  <<Aggregate Root>>
  -id
  -pedidoId
  -estado
  +aprobar()
  +rechazar(motivo)
  +reembolsar()
}
class Envio {
  <<Aggregate Root>>
  -id
  -pedidoId
  -guia
  -intentos
  +registrarEntrega()
  +registrarIntentoFallido(motivo)
}
class Devolucion {
  <<Aggregate Root>>
  -id
  -pedidoId
  +aprobar()
  +rechazar()
}

class AsignacionAlmacenService {
  <<Domain Service>>
  +asignar(lineas, almacenes) Surtidos
}
class PasarelaPago {
  <<Interface>>
  +cobrar(monto, metodo)
  +reembolsar(pagoId)
}
class PedidoRepository {
  <<Interface>>
}
class AlmacenRepository {
  <<Interface>>
}

PedidoAppService ..> PedidoRepository
PedidoAppService ..> AlmacenRepository
PedidoAppService ..> AsignacionAlmacenService
PedidoAppService ..> PagoAppService
PagoAppService ..> PasarelaPago
PagoAppService ..> Pago
PreparacionAppService ..> PedidoRepository
EnvioAppService ..> Envio
DevolucionAppService ..> Devolucion

Pedido "1" *-- "1..*" LineaPedido
Pedido "1" *-- "1..*" Surtido
Pedido *-- Dinero
Pedido *-- DireccionEntrega
Pedido --> EstadoPedido
Almacen "1" *-- "*" ExistenciaProducto
Pago ..> Pedido : pedidoId
Envio ..> Pedido : pedidoId
Devolucion ..> Pedido : pedidoId
Surtido ..> Almacen : almacenId
```

## Diagrama de secuencia 1: Checkout con pedido dividido y pago

```mermaid
sequenceDiagram
autonumber
actor Cliente
participant PS as PedidoAppService
participant AS as AsignacionAlmacenService
participant AR as AlmacenRepository
participant P as Pedido
participant PR as PedidoRepository
participant PG as PagoAppService
participant GW as PasarelaPago

Cliente->>PS: confirmarCheckout(carrito, direccion, modalidad, metodoPago)
PS->>AR: obtenerAlmacenes()
AR-->>PS: almacenes
PS->>AS: asignar(lineas, almacenes)
AS-->>PS: asignacion por almacén

alt Stock insuficiente en algún SKU
    PS-->>Cliente: error ProductoAgotado
else Stock disponible
    loop Por cada almacén asignado
        PS->>AR: reservar(sku, cantidad)
    end
    PS->>P: crear(lineas, direccion, modalidad)
    PS->>P: asignarSurtidos(asignacion)
    PS->>PR: guardar(pedido)
    PS->>PG: procesarPago(pedidoId, metodoPago)
    PG->>GW: cobrar(total, metodoPago)
    alt Pago aprobado
        GW-->>PG: aprobado
        PG->>P: marcarPagado()
        PG-->>PS: PedidoPagado
        PS-->>Cliente: pedido confirmado
    else Pago rechazado
        GW-->>PG: rechazado
        PG->>P: marcarPagoRechazado()
        loop Por cada reserva
            PS->>AR: liberar(sku, cantidad)
        end
        PS-->>Cliente: pago rechazado
    end
end
```

## Diagrama de secuencia 2: Cancelación antes del envío

```mermaid
sequenceDiagram
autonumber
actor Cliente
participant PS as PedidoAppService
participant PR as PedidoRepository
participant P as Pedido
participant AR as AlmacenRepository
participant PG as PagoAppService
participant GW as PasarelaPago

Cliente->>PS: cancelarPedido(pedidoId, motivo)
PS->>PR: obtener(pedidoId)
PR-->>PS: pedido
PS->>P: cancelar(motivo)

alt Estado Enviado o posterior
    P-->>PS: error CancelacionNoPermitida
    PS-->>Cliente: no se puede cancelar, ofrecer devolución
else Cancelación permitida
    P-->>PS: PedidoCancelado (con surtidos)
    loop Por cada surtido
        PS->>AR: liberar(sku, cantidad) en su almacén
    end
    opt Pedido ya pagado
        PS->>PG: procesarReembolso(pedidoId)
        PG->>GW: reembolsar(pagoId)
        GW-->>PG: reembolsado
    end
    PS->>PR: guardar(pedido)
    PS-->>Cliente: pedido cancelado
end
```

