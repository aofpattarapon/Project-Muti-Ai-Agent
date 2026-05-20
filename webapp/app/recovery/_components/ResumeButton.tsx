"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function ResumeButton({ sdlcTaskId }: { sdlcTaskId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleResume() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/runtime/paused-tasks/${sdlcTaskId}/resume`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { code?: string };
        setError(body.code ?? `HTTP ${res.status}`);
      } else {
        setDone(true);
        router.refresh();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return <span className="text-xs font-medium" style={{ color: "var(--ok)" }}>Queued</span>;
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleResume}
        disabled={loading}
        className="rounded-lg border px-3 py-1 text-xs font-semibold transition"
        style={{
          borderColor: "rgba(79,140,255,.4)",
          color: "#4f8cff",
          background: "rgba(79,140,255,.08)",
          opacity: loading ? 0.6 : 1,
          cursor: loading ? "not-allowed" : "pointer",
        }}
      >
        {loading ? "Queuing…" : "Resume"}
      </button>
      {error && (
        <span className="text-xs" style={{ color: "var(--bad)" }}>{error}</span>
      )}
    </div>
  );
}
