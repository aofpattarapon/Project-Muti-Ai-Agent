"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function LogoutButton() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleLogout() {
    setIsSubmitting(true);

    try {
      await fetch("/api/auth/logout", {
        method: "POST",
      });
      router.push("/login");
      router.refresh();
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <button
      className="material-chip inline-flex h-11 items-center justify-center rounded-2xl px-4 text-sm font-medium text-slate-200 transition hover:border-slate-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
      type="button"
      onClick={handleLogout}
      disabled={isSubmitting}
    >
      {isSubmitting ? "Signing out..." : "Logout"}
    </button>
  );
}
