"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username_or_email: usernameOrEmail,
          password,
        }),
      });

      const data = (await response.json()) as {
        message?: string;
        dashboard_route?: string;
      };

      if (!response.ok) {
        setError(data.message ?? "Unable to sign in.");
        return;
      }

      router.push(data.dashboard_route ?? "/dashboard");
      router.refresh();
    } catch {
      setError("Unable to sign in right now. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-6 py-12">
      <section className="w-full max-w-md rounded-[2rem] border border-slate-200 bg-white p-8 shadow-[0_25px_70px_-30px_rgba(15,23,42,0.35)]">
        <div className="space-y-3">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-sky-700">
            Sign in
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">
            Access the pilot dashboard
          </h1>
          <p className="text-sm leading-6 text-slate-600">
            Use a seeded Admin, Operator, or Viewer account to validate role-based access.
          </p>
        </div>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">Username or email</span>
            <input
              className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
              name="username_or_email"
              value={usernameOrEmail}
              onChange={(event) => setUsernameOrEmail(event.target.value)}
              autoComplete="username"
              placeholder="admin or admin@example.com"
            />
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-slate-950 outline-none transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
              type="password"
              name="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="Enter your password"
            />
          </label>

          {error ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <button
            className="inline-flex h-12 w-full items-center justify-center rounded-full bg-slate-950 px-5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="mt-8 rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
          <p className="font-medium text-slate-800">Seeded pilot users</p>
          <ul className="mt-3 space-y-1">
            <li>Admin: admin / Admin123!</li>
            <li>Operator: operator / Operator123!</li>
            <li>Viewer: viewer / Viewer123!</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
