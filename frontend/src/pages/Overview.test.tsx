import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { OverviewPage } from "./Overview";

vi.mock("../api/hooks", () => ({
  useStatements: () => ({
    data: [{ id: 1, period_start: "2026-09-01", period_end: "2026-09-30" }],
  }),
  useSummary: () => ({
    data: {
      total_debit_kurus: 5000,
      total_credit_kurus: 0,
      prev_total_debit_kurus: 1000,
      by_category: [{ key: "market", label_tr: "Market", kurus: 5000, count: 2 }],
      daily: [{ date: "2026-09-01", debit_kurus: 5000 }],
      top: [
        {
          id: 1,
          txn_date: "2026-09-01",
          merchant_norm: "MARKET",
          amount_kurus: 5000,
          effective_category: "market",
        },
      ],
    },
  }),
}));

vi.mock("./DailyChart", () => ({
  default: () => <div>chart</div>,
}));

afterEach(() => {
  cleanup();
});

test("overview uses last statement period", () => {
  render(<OverviewPage />);
  expect(screen.getByDisplayValue("2026-09-01")).toBeInTheDocument();
  expect(screen.getByDisplayValue("2026-09-30")).toBeInTheDocument();
});
