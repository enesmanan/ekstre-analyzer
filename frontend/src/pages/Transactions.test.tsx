import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { TransactionsPage } from "./Transactions";

const mocks = vi.hoisted(() => ({
  patch: vi.fn(async () => ({})),
}));

vi.mock("../api/hooks", () => ({
  useTransactions: () => ({
    data: {
      items: [
        {
          id: 1,
          statement_id: 1,
          txn_date: "2026-09-01",
          description: "Market",
          amount_kurus: 1000,
          currency: "TRY",
          direction: "debit",
          category: "market",
          user_override_category: null,
          effective_category: "market",
          merchant_norm: "MARKET",
          confidence: 0.9,
          is_installment: 0,
          installment_no: null,
          installment_total: null,
        },
      ],
      total: 1,
    },
  }),
  useCategories: () => ({
    data: [
      { key: "market", label_tr: "Market", sort: 0 },
      { key: "ulasim", label_tr: "Ulaşım", sort: 1 },
    ],
  }),
  usePatchTransaction: () => ({
    mutateAsync: mocks.patch,
  }),
}));

function wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  cleanup();
  mocks.patch.mockClear();
});

test("patching category invalidates via mutation", async () => {
  const user = userEvent.setup();
  render(wrap(<TransactionsPage />));
  await user.selectOptions(screen.getByDisplayValue("Market"), "ulasim");
  expect(mocks.patch).toHaveBeenCalledWith({ id: 1, category: "ulasim" });
});
