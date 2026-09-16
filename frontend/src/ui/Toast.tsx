import { useEffect, useState } from "react";

export function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onDone();
    }, 4000);
    return () => clearTimeout(timer);
  }, [onDone]);
  if (!visible) {
    return null;
  }
  return (
    <div role="status" className="fixed bottom-4 right-4 rounded bg-zinc-800 px-3 py-2 text-[13px] text-white">
      {message}
    </div>
  );
}
