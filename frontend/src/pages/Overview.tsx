import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useStatements, useSummary } from "../api/hooks";
import { formatKurus } from "../lib/money";
import { DateRange, Table } from "../ui";

const DailyChart = lazy(() => import("./DailyChart"));

function currentMonth(): { from: string; to: string } {
  const now = new Date();
  const from = new Date(now.getFullYear(), now.getMonth(), 1);
  const to = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
}

export function OverviewPage() {
  const statements = useStatements();
  const defaults = useMemo(() => {
    const last = statements.data?.[0];
    if (last?.period_start && last.period_end) {
      return { from: last.period_start, to: last.period_end };
    }
    return currentMonth();
  }, [statements.data]);
  const [range, setRange] = useState(defaults);
  useEffect(() => {
    setRange(defaults);
  }, [defaults]);
  const usedRange = range.from && range.to ? range : defaults;
  const summary = useSummary(usedRange.from, usedRange.to);
  const data = summary.data;
  const delta = data ? data.total_debit_kurus - data.prev_total_debit_kurus : 0;

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-[22px]">Genel bakış</h1>
      <DateRange from={usedRange.from} to={usedRange.to} onChange={setRange} />
      {data ? (
        <>
          <p className="text-[22px]">{formatKurus(data.total_debit_kurus)}</p>
          <p className="text-[13px]">Önceki döneme göre {formatKurus(delta)}</p>
          <ul>
            {data.by_category.map((bucket) => (
              <li key={bucket.key}>
                {bucket.label_tr}: {formatKurus(bucket.kurus)} ({bucket.count})
              </li>
            ))}
          </ul>
          <Suspense fallback={<p>Grafik yükleniyor</p>}>
            <DailyChart
              labels={data.daily.map((point) => point.date)}
              values={data.daily.map((point) => point.debit_kurus)}
            />
          </Suspense>
          <Table>
            <thead>
              <tr>
                <th>Tarih</th>
                <th>İşyeri</th>
                <th>Tutar</th>
                <th>Kategori</th>
              </tr>
            </thead>
            <tbody>
              {data.top.map((row) => (
                <tr key={row.id}>
                  <td>{row.txn_date}</td>
                  <td>{row.merchant_norm}</td>
                  <td>{formatKurus(row.amount_kurus)}</td>
                  <td>{row.effective_category}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      ) : null}
    </div>
  );
}
