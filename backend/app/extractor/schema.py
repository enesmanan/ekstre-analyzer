"""Extraction JSON schema and the fixed category set."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

CATEGORIES: tuple[str, ...] = (
    "market",
    "restoran_kafe",
    "ulasim",
    "yakit",
    "fatura_abonelik",
    "kira_konut",
    "saglik",
    "egitim",
    "giyim",
    "elektronik",
    "eglence",
    "seyahat",
    "nakit_cekim",
    "transfer",
    "kredi_odeme",
    "sigorta",
    "vergi_harc",
    "diger",
)

Category = Literal[
    "market",
    "restoran_kafe",
    "ulasim",
    "yakit",
    "fatura_abonelik",
    "kira_konut",
    "saglik",
    "egitim",
    "giyim",
    "elektronik",
    "eglence",
    "seyahat",
    "nakit_cekim",
    "transfer",
    "kredi_odeme",
    "sigorta",
    "vergi_harc",
    "diger",
]

CATEGORY_LABELS: dict[str, str] = {
    "market": "Market",
    "restoran_kafe": "Restoran / Kafe",
    "ulasim": "Ulaşım",
    "yakit": "Yakıt",
    "fatura_abonelik": "Fatura / Abonelik",
    "kira_konut": "Kira / Konut",
    "saglik": "Sağlık",
    "egitim": "Eğitim",
    "giyim": "Giyim",
    "elektronik": "Elektronik",
    "eglence": "Eğlence",
    "seyahat": "Seyahat",
    "nakit_cekim": "Nakit Çekim",
    "transfer": "Transfer",
    "kredi_odeme": "Kredi Ödeme",
    "sigorta": "Sigorta",
    "vergi_harc": "Vergi / Harç",
    "diger": "Diğer",
}

StatementType = Literal["card", "account", "unknown"]
Direction = Literal["debit", "credit"]


class Txn(BaseModel):
    txn_date: date
    description: str
    amount_kurus: int
    direction: Direction
    category: Category
    merchant_norm: str
    is_installment: bool
    installment_no: int | None = None
    installment_total: int | None = None
    confidence: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    bank: str
    statement_type: StatementType
    period_start: date
    period_end: date
    stated_total_debit_kurus: int | None
    transactions: list[Txn]


def gemini_json_schema(model: type[BaseModel] = Extraction) -> dict[str, Any]:
    """JSON schema with keys that Gemini may reject removed."""

    schema = model.model_json_schema()

    def _strip(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("title", None)
            node.pop("default", None)
            for value in node.values():
                _strip(value)
        elif isinstance(node, list):
            for item in node:
                _strip(item)

    _strip(schema)
    return schema
