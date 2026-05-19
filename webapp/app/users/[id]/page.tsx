import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { findUserById, USER_ROLES } from "@/lib/auth/query-users";

type UserDetailPageProps = {
  params: Promise<{ id: string }>;
};

export default async function UserDetailPage({ params }: UserDetailPageProps) {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const { id } = await params;
  const user = findUserById(id);

  if (!user) {
    notFound();
  }

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
                Admin Users
              </p>
              <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">{user.name}</h1>
              <p className="mt-3 text-sm leading-7 material-muted">
                Administrative user profile view for the pilot environment.
              </p>
            </div>
            <Link href="/users" className="oc-btn-ghost shrink-0">Back to users</Link>
          </div>
        </section>

        <section className="material-panel rounded-[2rem] p-8">
          <dl className="grid gap-6 sm:grid-cols-2">
            {[
              { label: "Full name", value: user.name },
              { label: "Username",  value: user.username },
              { label: "Email",     value: user.email },
            ].map(({ label, value }) => (
              <div key={label}>
                <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</dt>
                <dd className="mt-2 text-base text-slate-200">{value}</dd>
              </div>
            ))}

            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Role</dt>
              <dd className="mt-2"><span className="oc-badge">{user.role}</span></dd>
            </div>

            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Status</dt>
              <dd className="mt-2">
                <span className="oc-badge"
                  style={user.isActive
                    ? { color: "var(--ok)", background: "rgba(36,224,138,0.1)", borderColor: "rgba(36,224,138,0.25)" }
                    : { color: "var(--bad)", background: "rgba(255,92,92,0.1)", borderColor: "rgba(255,92,92,0.25)" }
                  }
                >
                  {user.isActive ? "Active" : "Inactive"}
                </span>
              </dd>
            </div>

            <div>
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">MFA status</dt>
              <dd className="mt-2 space-y-2">
                <span className="oc-badge"
                  style={user.mfaEnabled
                    ? { color: "#60a5fa", background: "rgba(96,165,250,0.1)", borderColor: "rgba(96,165,250,0.25)" }
                    : { color: "var(--warn)", background: "rgba(245,158,11,0.1)", borderColor: "rgba(245,158,11,0.25)" }
                  }
                >
                  {user.mfaEnabled ? "Enrolled" : "Not enrolled"}
                </span>
                <p className="text-sm material-muted mt-2">
                  {user.mfaEnrolledAt
                    ? `Enrolled at ${new Date(user.mfaEnrolledAt).toLocaleString()}`
                    : "No MFA enrollment has been recorded yet."}
                </p>
              </dd>
            </div>

            <div className="sm:col-span-2">
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Change role</dt>
              <dd className="mt-3">
                <form
                  action={`/api/admin/users/${user.id}/role`}
                  method="post"
                  className="flex flex-wrap items-center gap-3"
                >
                  <select name="role" defaultValue={user.role} className="oc-input" style={{ width: "auto" }}>
                    {USER_ROLES.map((role) => (
                      <option key={role} value={role}>{role}</option>
                    ))}
                  </select>
                  <button type="submit" className="oc-btn-action">Update role</button>
                </form>
              </dd>
            </div>

            <div className="sm:col-span-2">
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Admin action</dt>
              <dd className="mt-3">
                <form action={`/api/admin/users/${user.id}/status`} method="post">
                  <input type="hidden" name="is_active" value={user.isActive ? "false" : "true"} />
                  <button type="submit" className={user.isActive ? "oc-btn-danger" : "oc-btn-ok"}>
                    {user.isActive ? "Deactivate user" : "Activate user"}
                  </button>
                </form>
              </dd>
            </div>

            <div className="sm:col-span-2">
              <dt className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">Pilot note</dt>
              <dd className="mt-2 text-sm leading-7 material-muted">
                MFA state is now modeled for readiness and visibility, but login still uses the
                current single-step flow until a future MFA phase adds real verification.
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </main>
  );
}
