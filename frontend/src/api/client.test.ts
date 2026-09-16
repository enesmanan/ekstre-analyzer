import { afterEach, expect, test, vi } from "vitest";
import { ApiClientError, api, uploadStatement } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("parses error.code from envelope", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ error: { code: "password_required", message: "şifre", issues: [] } }),
    })),
  );
  await expect(api("/api/v1/statements")).rejects.toMatchObject({
    code: "password_required",
  } satisfies Partial<ApiClientError>);
});

test("upload sends raw pdf body not FormData", async () => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    expect(init?.body).toBeInstanceOf(Blob);
    expect(init?.body instanceof FormData).toBe(false);
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/pdf");
    return {
      ok: true,
      status: 202,
      json: async () => ({ id: 1 }),
    };
  });
  vi.stubGlobal("fetch", fetchMock);
  const file = new File(["%PDF-1.4"], "t.pdf", { type: "application/pdf" });
  await uploadStatement(file, "secret");
  expect(fetchMock).toHaveBeenCalled();
});
