import { Input } from "./controls";

export function DateRange({
  from,
  to,
  onChange,
}: {
  from: string;
  to: string;
  onChange: (next: { from: string; to: string }) => void;
}) {
  const invalid = Boolean(from && to && from > to);
  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="text-[13px]">
        Başlangıç
        <Input type="date" value={from} onChange={(event) => onChange({ from: event.target.value, to })} />
      </label>
      <label className="text-[13px]">
        Bitiş
        <Input type="date" value={to} onChange={(event) => onChange({ from, to: event.target.value })} />
      </label>
      {invalid ? <p className="text-[13px] text-red-600">Geçersiz tarih aralığı</p> : null}
    </div>
  );
}
