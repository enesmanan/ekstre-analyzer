import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test } from "vitest";
import { UploadPage } from "./Upload";

function wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  cleanup();
});

test("rejects non-pdf files on the client", () => {
  render(wrap(<UploadPage />));
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["hello"], "note.txt", { type: "text/plain" });
  fireEvent.change(input, { target: { files: [file] } });
  expect(screen.getByText("Yalnızca PDF yükleyin")).toBeInTheDocument();
});
