import Link from "next/link";
import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { listUsers } from "@/lib/auth/query-users";

export default async function UsersPage() {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const users = listUsers();

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
                Admin Users
              </p>
              <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
                User directory
              </h1>
              <p className="mt-3 text-sm leading-7 material-muted">
                Administrative view of user access, role, and MFA readiness in the pilot environment.
              </p>
            </div>
            <Link href="/dashboard" className="oc-btn-ghost shrink-0">Back to dashboard</Link>
          </div>
        </section>

        <section className="material-panel overflow-hidden rounded-[2rem]">
          <div className="border-b border-[rgba(255,255,255,0.06)] px-6 py-4">
            <h2 className="text-base font-semibold text-white">Current users</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="oc-table">
              <thead>
                <tr>
                  {["Name", "Username", "Email", "Role", "Status", "MFA"].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="oc-td-primary">
                      <Link href={`/users/${user.id}`} className="transition hover:text-[#4f8cff]">
                        {user.name}
                      </Link>
                    </td>
                    <td>{user.username}</td>
                    <td>{user.email}</td>
                    <td><span className="oc-badge">{user.role}</span></td>
                    <td>
                      <span className="oc-badge"
                        style={user.isActive
                          ? { color: "var(--ok)", background: "rgba(36,224,138,0.1)", borderColor: "rgba(36,224,138,0.25)" }
                          : { color: "var(--bad)", background: "rgba(255,92,92,0.1)", borderColor: "rgba(255,92,92,0.25)" }
                        }
                      >
                        {user.isActive ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>
                      <span className="oc-badge"
                        style={user.mfaEnabled
                          ? { color: "#60a5fa", background: "rgba(96,165,250,0.1)", borderColor: "rgba(96,165,250,0.25)" }
                          : { color: "var(--warn)", background: "rgba(245,158,11,0.1)", borderColor: "rgba(245,158,11,0.25)" }
                        }
                      >
                        {user.mfaEnabled ? "Enrolled" : "Not enrolled"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
