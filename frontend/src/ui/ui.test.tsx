import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { DateRange, Dialog, Toast } from "../ui";

afterEach(() => {
  cleanup();
});

test("dialog closes on escape and keeps focus", async () => {
  const user = userEvent.setup();
  function Harness() {
    const [open, setOpen] = useState(true);
    return (
      <Dialog open={open} title="Test" onClose={() => setOpen(false)}>
        <button type="button">İçeride</button>
      </Dialog>
    );
  }
  render(<Harness />);
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("toast disappears after 4 seconds", () => {
  vi.useFakeTimers();
  const onDone = vi.fn();
  render(<Toast message="Kaydedildi" onDone={onDone} />);
  expect(screen.getByRole("status")).toHaveTextContent("Kaydedildi");
  vi.advanceTimersByTime(4000);
  expect(onDone).toHaveBeenCalled();
  vi.useRealTimers();
});

test("date range shows error when invalid", async () => {
  const user = userEvent.setup();
  function Harness() {
    const [range, setRange] = useState({ from: "2026-09-10", to: "2026-09-01" });
    return <DateRange from={range.from} to={range.to} onChange={setRange} />;
  }
  render(<Harness />);
  expect(screen.getByText("Geçersiz tarih aralığı")).toBeInTheDocument();
  await user.clear(screen.getAllByDisplayValue("2026-09-01")[0]);
});
