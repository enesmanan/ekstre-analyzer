import { useMemo, useState } from "react";
import { useCategories, usePatchTransaction, useTransactions } from "../api/hooks";
import { formatKurus } from "../lib/money";
import { Input, Select, Table } from "../ui";

export function TransactionsPage() {
  const [q, setQ] = useState("");
  const [direction, setDirection] = useState("");
  const [category, setCategory] = useState("");
  const params = useMemo(() => {
    const search = new URLSearchParams();
    if (q) {
      search.set("q", q);
    }
    if (direction) {
      search.set("direction", direction);
    }
    if (category) {
      search.set("category", category);
    }
    return search;
  }, [q, direction, category]);
  const list = useTransactions(params);
  const categories = useCategories();
  const patch = usePatchTransaction();

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-[22px]">İşlemler</h1>
      <div className="flex flex-wrap gap-2">
        <Input placeholder="Ara" value={q} onChange={(event) => setQ(event.target.value)} />
        <Select value={direction} onChange={(event) => setDirection(event.target.value)}>
          <option value="">Yön</option>
          <option value="debit">Gider</option>
          <option value="credit">Gelir</option>
        </Select>
        <Select value={category} onChange={(event) => setCategory(event.target.value)}>
          <option value="">Kategori</option>
          {(categories.data ?? []).map((item) => (
            <option key={item.key} value={item.key}>
              {item.label_tr}
            </option>
          ))}
        </Select>
      </div>
      <Table>
        <thead>
          <tr>
            <th>Tarih</th>
            <th>Açıklama</th>
            <th>Tutar</th>
            <th>Kategori</th>
          </tr>
        </thead>
        <tbody>
          {(list.data?.items ?? []).map((row) => (
            <tr key={row.id}>
              <td>{row.txn_date}</td>
              <td>{row.description}</td>
              <td>{formatKurus(row.amount_kurus)}</td>
              <td>
                <Select
                  value={row.effective_category}
                  onChange={(event) => {
                    const value = event.target.value;
                    void patch.mutateAsync({ id: row.id, category: value || null });
                  }}
                >
                  {(categories.data ?? []).map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label_tr}
                    </option>
                  ))}
                </Select>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
