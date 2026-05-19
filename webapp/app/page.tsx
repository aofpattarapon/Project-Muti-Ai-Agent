export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,#eff6ff,transparent_35%),linear-gradient(180deg,#f8fafc_0%,#eef2ff_100%)] px-6 py-16">
      <section className="w-full max-w-4xl rounded-[2rem] border border-slate-200/70 bg-white/90 p-8 shadow-[0_30px_80px_-30px_rgba(15,23,42,0.25)] backdrop-blur sm:p-12">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr] lg:items-end">
          <div className="space-y-6">
            <span className="inline-flex rounded-full border border-sky-200 bg-sky-50 px-4 py-1 text-sm font-medium text-sky-700">
              Pilot Slice
            </span>
            <div className="space-y-4">
              <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl">
                Login, role-based access, and a basic dashboard for the SDLC pilot.
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-slate-600">
                This MVP proves authenticated entry, backend-enforced role access,
                dashboard landing, logout, and audit-aware behavior in one simple
                product slice.
              </p>
            </div>
            <div className="flex flex-col gap-4 sm:flex-row">
              <a
                className="inline-flex h-12 items-center justify-center rounded-full bg-slate-950 px-6 text-sm font-medium text-white transition hover:bg-slate-800"
                href="/login"
              >
                Open Login
              </a>
              <a
                className="inline-flex h-12 items-center justify-center rounded-full border border-slate-300 px-6 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
                href="/dashboard"
              >
                View Dashboard
              </a>
            </div>
          </div>
          <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-6">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-500">
              Included
            </p>
            <ul className="mt-5 space-y-3 text-sm leading-6 text-slate-700">
              <li>Username or email login</li>
              <li>Admin, Operator, and Viewer roles</li>
              <li>Protected dashboard route</li>
              <li>Logout and session reset</li>
              <li>Basic audit event recording</li>
            </ul>
          </div>
        </div>
      </section>
    </main>
  );
}
