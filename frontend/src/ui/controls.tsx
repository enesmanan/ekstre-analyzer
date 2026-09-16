import type { ButtonHTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes } from "react";

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`rounded px-3 py-1.5 text-[15px] bg-[var(--accent)] text-white disabled:opacity-50 ${props.className ?? ""}`}
    />
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`rounded border border-zinc-400 bg-transparent px-2 py-1 text-[15px] ${props.className ?? ""}`}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`rounded border border-zinc-400 bg-transparent px-2 py-1 text-[15px] ${props.className ?? ""}`}
    />
  );
}
