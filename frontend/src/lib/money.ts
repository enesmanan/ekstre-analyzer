const formatter = new Intl.NumberFormat("tr-TR", {
  style: "currency",
  currency: "TRY",
  minimumFractionDigits: 2,
});

export function formatKurus(kurus: number): string {
  return formatter.format(kurus / 100);
}
