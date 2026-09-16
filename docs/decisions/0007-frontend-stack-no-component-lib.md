# ADR-0007: Vite + React + TS, component kütüphanesi yok

Durum: kabul edildi · Tarih: 2026-09-16 · İlgili faz: Faz 3

## Bağlam ve problem

Sade, hızlı, tek geliştiricinin sürdürebileceği bir dashboard. Hazır component kütüphaneleri hız kazandırır ama görsel kimliği ve bundle'ı şişirir.

## Değerlendirilen seçenekler

- Vite + React 19 + TS, Tailwind v4 utility, kendi 8 primitif
- shadcn/ui (Radix tabanlı, kopyala-yapıştır)
- MUI / Mantine
- Svelte / SolidJS (daha küçük bundle, ama ekosistem ve deneyim)

## Karar

"Kendi primitifler", çünkü ürün 4 ekran ve 8 bileşenden oluşuyor; kütüphane öğrenme ve override maliyeti bunları yazmaktan fazla. Görsel dil: tek font ailesi, 3 boyut, gri skala + tek vurgu rengi, gradient/emoji/kart-içinde-kart yok.

Uygulama kuralları:

- Paketler: `vite@8`, `react@19`, `react-dom@19`, `react-router@8` (`react-router-dom` artık yok; `RouterProvider` için `react-router/dom`), `@tanstack/react-query@5`, `tailwindcss@4` + `@tailwindcss/vite`, `uplot@1.6`, `typescript@7` (sorun çıkarsa 6.x).
- react-router **Data mode** (`createBrowserRouter`), loader'lar yerine TanStack Query.
- Node ≥ 22.22 (react-router 8 şartı); hedef Node 24.
- Grafik: uPlot, `React.lazy` ile sadece genel bakış sayfasında yüklenir.
- Bundle hedefi: ilk yükleme < 250 KB gz (kütüphaneler ~165 KB).

## Sonuçlar

- İyi: Küçük bundle, tam görsel kontrol, bağımlılık azlığı.
- Kötü: Dialog, Toast ve DateRange gibi erişilebilirlik gerektiren bileşenler zaman alır; Faz 3 süresi buna göre 3 hafta. Erişilebilirlik (ARIA, klavye) testleri manuel.
- Doğrulama tarihi ve kaynak: 2026-09-16, https://reactrouter.com/changelog , https://tailwindcss.com/docs/installation/using-vite , https://vite.dev/guide/
