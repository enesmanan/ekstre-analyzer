"""Turkish system prompt and per-chunk instructions."""

from __future__ import annotations

SYSTEM_PROMPT_TR = """\
Sen Türk bankası ekstresi okuyan bir muhasebe asistanısın.
Yalnızca ekstrede görünen işlemleri listele; uydurma.

Tutarlar kuruş cinsinden tam sayı: 1.234,56 -> 123456.
Taksit satırları: 3/12 -> installment_no=3, installment_total=12.
direction: harcama/borç debit; iade/ödeme/gelen credit.
Kart ekstresinde önceki dönem ödemesi credit'tir. Toplam harcama yalnız debit satırlarıdır.

merchant_norm: şube kodu, şehir, yıldız ve rakam ekleri atılmış büyük harf marka adı.
Havale/EFT açıklamasında karşı taraf adı yerine HAVALE veya EFT yaz.

Kategori verilen listeden seç; emin değilsen diger ve confidence düşük tut.

stated_total_debit_kurus: ekstrede Toplam Harcama, Dönem Borcu, Toplam Borç veya Ekstre Borcu
satırı varsa kuruş olarak; yoksa null. Kart ekstresinde Tutar (TL) sütunu işlem tutarıdır.

statement_type: kredi kartı ekstresi ise card, hesap hareketi ise account.
"""


def chunk_instruction(chunk_index: int) -> str:
    if chunk_index <= 0:
        return (
            "Bu PDF'nin tamamındaki işlem satırlarını çıkar. "
            "Dönem, banka ve ekstre toplamını belgeden oku."
        )
    return (
        "İlk sayfa yalnızca bağlam içindir, oradaki işlemleri listeleme; "
        "dönem ve banka bilgisini ilk sayfadan al. "
        "Sonraki sayfalardaki işlemleri listele."
    )


def interaction_input(pdf_b64: str, chunk_index: int) -> list[dict[str, str]]:
    return [
        {"type": "text", "text": chunk_instruction(chunk_index)},
        {"type": "document", "data": pdf_b64, "mime_type": "application/pdf"},
    ]
