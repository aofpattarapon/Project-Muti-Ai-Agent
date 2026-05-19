"use client";

import Link from "next/link";
import { FormEvent, use, useState } from "react";

type ResetPasswordTokenPageProps = {
  params: Promise<{
    token: string;
  }>;
};

export default function ResetPasswordTokenPage({ params }: ResetPasswordTokenPageProps) {
  const { token } = use(params);

  return <ResetPasswordTokenForm token={token} />;
}

function ResetPasswordTokenForm({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setMessage("");
    setErrorMessage("");

    const response = await fetch("/api/auth/password-reset/confirm", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        token,
        password,
        confirm_password: confirmPassword,
      }),
    });

    const payload = (await response.json()) as {
      success: boolean;
      message?: string;
    };

    if (!response.ok) {
      setErrorMessage(payload.message ?? "Unable to complete password reset.");
      setIsSubmitting(false);
      return;
    }

    setMessage(payload.message ?? "Password updated successfully.");
    setPassword("");
    setConfirmPassword("");
    setIsSubmitting(false);
  }

  return (
    <main className="min-h-screen bg-slate-100 px-6 py-10 text-slate-900">
      <div className="mx-auto max-w-xl rounded-[2rem] border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">
          Password Reset
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Choose a new password</h1>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          Use a new password with at least 8 characters to complete the reset flow.
        </p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label
              htmlFor="password"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              New password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none transition focus:border-slate-500"
            />
          </div>

          <div>
            <label
              htmlFor="confirm_password"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              Confirm password
            </label>
            <input
              id="confirm_password"
              name="confirm_password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="w-full rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none transition focus:border-slate-500"
            />
          </div>

          {message ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {message}
            </div>
          ) : null}

          {errorMessage ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {errorMessage}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isSubmitting ? "Updating..." : "Update password"}
            </button>

            <Link
              href="/login"
              className="rounded-full border border-slate-300 bg-white px-5 py-3 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
            >
              Back to login
            </Link>
          </div>
        </form>
      </div>
    </main>
  );
}
