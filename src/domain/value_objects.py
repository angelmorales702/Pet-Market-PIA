"""Value Objects del dominio PetMarket.

Los Value Objects son inmutables, identificados por sus atributos (no por identidad).
No dependen de FastAPI, SQLAlchemy ni de ningún framework externo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from uuid import UUID, uuid4


class Sku(str):
    """SKU (Stock Keeping Unit) - identificador único de un producto.

    # SUPUESTO: formato SKU-XXXXX con 5 dígitos. Validar con el negocio.
    """

    @classmethod
    def of(cls, value: str) -> "Sku":
        if not value or not isinstance(value, str):
            raise ValueError("SKU no puede ser vacío")
        normalized = value.strip().upper()
        if not normalized.startswith("SKU-"):
            raise ValueError(f"SKU '{value}' no cumple el formato SKU-XXXXX")
        digits_part = normalized[4:]
        if not digits_part.isdigit() or len(digits_part) != 5:
            raise ValueError(f"SKU '{value}' no cumple el formato SKU-XXXXX (debe tener exactamente 5 dígitos)")
        return cls(normalized)


class EstadoSurtido(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_PREPARACION = "EN_PREPARACION"
    EMPACADO = "EMPACADO"


class EstadoPago(str, Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class EstadoEnvio(str, Enum):
    PENDIENTE = "PENDIENTE"
    EN_TRASITO = "EN_TRASITO"
    ENTREGADO = "ENTREGADO"
    FALLIDO = "FALLIDO"


class EstadoDevolucion(str, Enum):
    SOLICITADA = "SOLICITADA"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"
    PROCESADA = "PROCESADA"


@dataclass(frozen=True)
class Dinero:
    """Representa un monto monetario en una moneda específica.

    Utiliza Decimal para evitar problemas de precisión de punto flotante.
    """
    monto: Decimal
    moneda: str = "MXN"

    def __post_init__(self) -> None:
        if not isinstance(self.monto, Decimal):
            try:
                object.__setattr__(self, "monto", Decimal(str(self.monto)))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"Monto inválido: {self.monto}") from exc
        if self.monto < 0:
            raise ValueError("El monto no puede ser negativo")
        if not self.moneda or not isinstance(self.moneda, str):
            raise ValueError("La moneda debe ser un texto no vacío")

    def __add__(self, other: "Dinero") -> "Dinero":
        if self.moneda != other.moneda:
            raise ValueError("No se pueden sumar montos en monedas distintas")
        return Dinero(self.monto + other.monto, self.moneda)

    def __sub__(self, other: "Dinero") -> "Dinero":
        if self.moneda != other.moneda:
            raise ValueError("No se pueden restar montos en monedas distintas")
        return Dinero(self.monto - other.monto, self.moneda)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Dinero):
            return NotImplemented
        return self.monto == other.monto and self.moneda == other.moneda

    def __hash__(self) -> int:
        return hash((self.monto, self.moneda))

    def __gt__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise ValueError("No se pueden comparar montos en monedas distintas")
        return self.monto > other.monto

    def __ge__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise ValueError("No se pueden comparar montos en monedas distintas")
        return self.monto >= other.monto

    def __lt__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise ValueError("No se pueden comparar montos en monedas distintas")
        return self.monto < other.monto

    def __le__(self, other: "Dinero") -> bool:
        if self.moneda != other.moneda:
            raise ValueError("No se pueden comparar montos en monedas distintas")
        return self.monto <= other.monto


@dataclass(frozen=True)
class DireccionEntrega:
    """Dirección física donde se entregarán los productos del pedido.

    # SUPUESTO: La dirección debe incluir al menos calle, número, colonia, ciudad y código postal.
    # Validar con el negocio.
    """
    calle: str
    numero: str
    colonia: str
    ciudad: str
    codigo_postal: str

    def __post_init__(self) -> None:
        for attr in ("calle", "numero", "colonia", "ciudad", "codigo_postal"):
            value = getattr(self, attr)
            if not value or not isinstance(value, str) or not value.strip():
                raise ValueError(f"La dirección debe tener {attr} no vacío")
        cp = self.codigo_postal.strip()
        if not cp.isdigit() or len(cp) != 5:
            raise ValueError("El código postal debe tener 5 dígitos numéricos")


@dataclass(frozen=True)
class Guia:
    """Guía de envío generada por el proveedor de transporte."""
    valor: str

    def __post_init__(self) -> None:
        if not self.valor or not isinstance(self.valor, str):
            raise ValueError("La guía no puede ser vacía")
        if not self.valor.strip():
            raise ValueError("La guía no puede ser vacía")

    @classmethod
    def of(cls, value: str) -> "Guia":
        return cls(value)


@dataclass(frozen=True)
class MotivoDevolucion:
    """Motivo de la devolución del pedido."""
    valor: str

    def __post_init__(self) -> None:
        if not self.valor or not isinstance(self.valor, str):
            raise ValueError("El motivo no puede ser vacío")
        if not self.valor.strip():
            raise ValueError("El motivo no puede ser vacío")

    @classmethod
    def of(cls, value: str) -> "MotivoDevolucion":
        return cls(value)


def new_id() -> UUID:
    """Genera un nuevo UUID v4."""
    return uuid4()