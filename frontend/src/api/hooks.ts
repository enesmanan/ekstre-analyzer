import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  type Category,
  type Statement,
  type Summary,
  type Transaction,
  uploadStatement,
} from "./client";

const ACTIVE = new Set(["queued", "masking", "extracting"]);

export function useStatements() {
  return useQuery({
    queryKey: ["statements"],
    queryFn: () => api<Statement[]>("/api/v1/statements"),
  });
}

export function useStatement(id: number | null) {
  return useQuery({
    queryKey: ["statements", id],
    queryFn: () => api<Statement>(`/api/v1/statements/${id}`),
    enabled: id !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status ?? "queued";
      return ACTIVE.has(status) ? 2000 : false;
    },
  });
}

export function useUpload() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ file, password }: { file: Blob; password?: string }) =>
      uploadStatement(file, password),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["statements"] });
    },
  });
}

export function useTransactions(params: URLSearchParams) {
  const qs = params.toString();
  return useQuery({
    queryKey: ["transactions", qs],
    queryFn: () => api<{ items: Transaction[]; total: number }>(`/api/v1/transactions?${qs}`),
  });
}

export function useSummary(from: string, to: string) {
  return useQuery({
    queryKey: ["summary", from, to],
    queryFn: () => api<Summary>(`/api/v1/summary?from=${from}&to=${to}`),
    enabled: Boolean(from && to),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/api/v1/categories"),
  });
}

export function usePatchTransaction() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, category }: { id: number; category: string | null }) =>
      api<Transaction>(`/api/v1/transactions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category }),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["transactions"] });
      void client.invalidateQueries({ queryKey: ["summary"] });
    },
  });
}
