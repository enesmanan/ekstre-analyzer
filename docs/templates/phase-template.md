# Faz N — <Başlık>

| Durum | Tarih | Süre tahmini | Bağımlılık |
|---|---|---|---|
| taslak / onaylı / uygulanıyor / bitti | YYYY-AA-GG | X hafta | Faz N-1 bitti |

Önceki: [Faz N-1](faz-N-1-....md) · Sonraki: [Faz N+1](faz-N+1-....md) · İlgili ADR: [ADR-000X](../decisions/000X-....md)

## 1. Amaç

Tek paragraf: bu faz bitince ne çalışıyor olacak.

## 2. Kapsam / Kapsam dışı

- Kapsam: ...
- Kapsam dışı: ... (sonraki faza ertelenenler, link ver)

## 3. Ön koşullar

- [ ] Faz N-1 kabul kriterleri geçti
- [ ] Gerekli secret/env: `...` (`.env.example` içinde)

## 4. Teslimatlar

Somut çıktılar: komutlar, dosyalar, endpoint'ler.

## 5. Tasarım

### 5.1 Modüller (dosya yolları ile)
### 5.2 Veri modeli
### 5.3 API / CLI arayüzü
### 5.4 Bilinen tuzaklar

## 6. Görevler

Format: `- [ ] FN-TXX [P] Açıklama — dosya/yolu`. `[P]` = başka göreve bağımlı değil, paralel yapılabilir.
Her görevin altında doğrulama komutu.

### 6.1 Kurulum
- [ ] FN-T01 ... — `yol/dosya`
      Doğrula: `komut`

### 6.2 Çekirdek
### 6.3 Kapanış
- [ ] FN-TXX Bu dosyada Durum → bitti, changelog satırı ekle

## 7. Kabul kriterleri

- KK-1: Verildiğinde <durum>, <eylem> yapıldığında, <sonuç>. Komut: `...`

## 8. Riskler (bu faza özgü)

| Risk | Etki | Önlem |
|---|---|---|

## 9. Açık sorular

- [NETLEŞTİRİLMELİ: ...] ← ajan bunu tahmin etmez, kullanıcıya sorar

## 10. Referanslar

Resmi doküman URL'leri.

## Changelog

- YYYY-AA-GG taslak oluşturuldu
