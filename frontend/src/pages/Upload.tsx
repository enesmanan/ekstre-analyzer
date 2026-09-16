import { useState, type FormEvent } from "react";
import { ApiClientError } from "../api/client";
import { useStatement, useUpload } from "../api/hooks";
import { Button, Input } from "../ui";

const ACTIVE = new Set(["queued", "masking", "extracting"]);

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [statementId, setStatementId] = useState<number | null>(null);
  const upload = useUpload();
  const statement = useStatement(statementId);
  const passwordRequired = upload.error instanceof ApiClientError && upload.error.code === "password_required";
  const status = statement.data?.status ?? (statementId ? "queued" : null);

  function onPick(next: File | null) {
    setClientError(null);
    if (next && next.type !== "application/pdf" && !next.name.toLowerCase().endsWith(".pdf")) {
      setClientError("Yalnızca PDF yükleyin");
      setFile(null);
      return;
    }
    setFile(next);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setClientError("PDF seçin");
      return;
    }
    try {
      const created = await upload.mutateAsync({ file, password: password || undefined });
      setStatementId(created.id);
    } catch {
      /* envelope shown via upload.error */
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-xl space-y-4 p-4">
      <h1 className="text-[22px]">Ekstre yükle</h1>
      <label
        className="block cursor-pointer rounded border border-dashed border-zinc-400 p-6 text-center"
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          onPick(event.dataTransfer.files[0] ?? null);
        }}
      >
        {file ? file.name : "PDF sürükleyin veya seçin"}
        <input
          className="sr-only"
          type="file"
          accept="application/pdf"
          onChange={(event) => onPick(event.target.files?.[0] ?? null)}
        />
      </label>
      <label className={`block text-[13px] ${passwordRequired ? "text-red-600" : ""}`}>
        PDF şifresi
        <Input
          type="password"
          value={password}
          aria-invalid={passwordRequired}
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>
      {clientError ? <p className="text-red-600">{clientError}</p> : null}
      {upload.error instanceof ApiClientError ? <p className="text-red-600">{upload.error.message}</p> : null}
      <Button type="submit" disabled={upload.isPending}>
        Yükle
      </Button>
      {status ? <p>Durum: {status}{statement.data?.error ? ` (${statement.data.error})` : ""}</p> : null}
      {statementId && status && !ACTIVE.has(status) && status !== "mask_failed" && status !== "extract_failed" ? (
        <img alt="Maskelenmiş önizleme" src={`/api/v1/statements/${statementId}/preview.png`} />
      ) : null}
    </form>
  );
}
