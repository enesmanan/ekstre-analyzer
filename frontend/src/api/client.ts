export type ApiErrorBody = {
  error: { code: string; message: string; issues: unknown[] };
};

export class ApiClientError extends Error {
  code: string;
  issues: unknown[];

  constructor(code: string, message: string, issues: unknown[] = []) {
    super(message);
    this.code = code;
    this.issues = issues;
  }
}

async function parseError(response: Response): Promise<ApiClientError> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    return new ApiClientError(
      body.error?.code ?? "http_error",
      body.error?.message ?? response.statusText,
      body.error?.issues ?? [],
    );
  } catch {
    return new ApiClientError("http_error", response.statusText);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function uploadStatement(file: Blob, password?: string): Promise<{ id: number }> {
  const headers: Record<string, string> = { "Content-Type": "application/pdf" };
  if (password) {
    headers["X-Statement-Password"] = password;
  }
  return api<{ id: number }>("/api/v1/statements", { method: "POST", body: file, headers });
}

export type Statement = {
  id: number;
  status: string;
  error: string | null;
  issues: unknown[];
  period_start: string | null;
  period_end: string | null;
  page_count: number;
};

export type Transaction = {
  id: number;
  statement_id: number;
  txn_date: string;
  description: string;
  amount_kurus: number;
  currency: string;
  direction: string;
  category: string;
  user_override_category: string | null;
  effective_category: string;
  merchant_norm: string;
  confidence: number;
  is_installment: number;
  installment_no: number | null;
  installment_total: number | null;
};

export type Summary = {
  total_debit_kurus: number;
  total_credit_kurus: number;
  prev_total_debit_kurus: number;
  by_category: { key: string; label_tr: string; kurus: number; count: number }[];
  daily: { date: string; debit_kurus: number }[];
  top: {
    id: number;
    txn_date: string;
    merchant_norm: string;
    amount_kurus: number;
    effective_category: string;
  }[];
};

export type Category = { key: string; label_tr: string; sort: number };
