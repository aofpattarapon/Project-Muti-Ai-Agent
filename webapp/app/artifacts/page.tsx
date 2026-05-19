import Link from "next/link";
import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { getArtifactPackage, listArtifactPackages } from "@/lib/artifacts/catalog";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function firstValue(value: string | string[] | undefined) {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }
  return value ?? "";
}

export default async function ArtifactsPage(props: { searchParams: SearchParams }) {
  const session = await getSession();

  if (!session) {
    redirect("/login");
  }

  if (session.role !== "Admin") {
    redirect("/dashboard");
  }

  const searchParams = await props.searchParams;
  const packages = listArtifactPackages();
  const selectedProjectId = firstValue(searchParams.project) || packages[0]?.projectId || "";
  const selectedPackage = selectedProjectId ? getArtifactPackage(selectedProjectId) : null;

  return (
    <main className="px-5 py-6 lg:px-8 lg:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="material-panel rounded-[2rem] px-8 py-10">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#4f8cff]">
            Deliverables
          </p>
          <h1 className="material-title mt-2 text-4xl font-semibold tracking-tight">
            Artifact packages
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 material-muted">
            Browse SDLC output packages from the active Python runtime, open individual files,
            and export a full archive from the web control plane.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link href="/project-logs" className="oc-btn-ghost">
              Open project logs
            </Link>
            <Link href="/workboard" className="oc-btn-ghost">
              Open workboard
            </Link>
            {selectedPackage ? (
              <>
                <a
                  href={`/api/artifacts/export?project=${encodeURIComponent(selectedPackage.projectId)}&format=json`}
                  className="oc-btn-ghost"
                >
                  Export manifest JSON
                </a>
                <a
                  href={`/api/artifacts/export?project=${encodeURIComponent(selectedPackage.projectId)}&format=tgz`}
                  className="oc-btn-action"
                >
                  Download package
                </a>
              </>
            ) : null}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="material-panel rounded-[2rem] px-5 py-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-white">Packages</h2>
              <span className="oc-badge">{packages.length}</span>
            </div>
            <div className="mt-4 space-y-3">
              {packages.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-white/10 px-4 py-6 text-sm text-slate-400">
                  No runtime artifact packages found yet.
                </div>
              ) : (
                packages.map((pkg) => {
                  const active = pkg.projectId === selectedProjectId;

                  return (
                    <Link
                      key={pkg.projectId}
                      href={`/artifacts?project=${encodeURIComponent(pkg.projectId)}`}
                      className={`block rounded-3xl border px-4 py-4 transition ${
                        active
                          ? "border-[#4f8cff] bg-[rgba(79,140,255,0.12)]"
                          : "border-white/8 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05]"
                      }`}
                    >
                      <p className="text-sm font-semibold text-white">{pkg.projectName}</p>
                      <p className="mt-1 font-mono text-xs text-slate-400">{pkg.projectId}</p>
                      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-300">
                        <span className="oc-badge">{pkg.projectStatus}</span>
                        <span className="oc-badge">{pkg.fileCount} files</span>
                        <span className="oc-badge">{pkg.roles.length} roles</span>
                      </div>
                    </Link>
                  );
                })
              )}
            </div>
          </aside>

          <section className="material-panel overflow-hidden rounded-[2rem]">
            {selectedPackage ? (
              <>
                <div className="border-b border-[rgba(255,255,255,0.06)] px-6 py-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h2 className="text-2xl font-semibold text-white">{selectedPackage.projectName}</h2>
                      <p className="mt-1 font-mono text-sm text-slate-400">{selectedPackage.projectId}</p>
                      <p className="mt-3 text-sm text-slate-400">
                        Status: <span className="text-white">{selectedPackage.projectStatus}</span>
                        {" · "}
                        Current role: <span className="text-white">{selectedPackage.currentRole}</span>
                      </p>
                      <p className="mt-2 text-xs text-slate-500">{selectedPackage.packagePath}</p>
                    </div>

                    <div className="flex flex-wrap gap-3 text-sm">
                      <a
                        href={`/api/artifacts/export?project=${encodeURIComponent(selectedPackage.projectId)}&format=tgz`}
                        className="oc-btn-action"
                      >
                        Download package
                      </a>
                      <a
                        href={`/api/artifacts/export?project=${encodeURIComponent(selectedPackage.projectId)}&format=json`}
                        className="oc-btn-ghost"
                      >
                        Manifest JSON
                      </a>
                    </div>
                  </div>
                </div>

                <div className="grid gap-6 px-6 py-6 xl:grid-cols-[280px_minmax(0,1fr)]">
                  <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.03] p-4">
                    <h3 className="text-sm font-semibold text-white">Role coverage</h3>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedPackage.roles.map((role) => (
                        <span key={role} className="oc-badge">
                          {role}
                        </span>
                      ))}
                    </div>
                    <dl className="mt-5 space-y-3 text-sm">
                      <div>
                        <dt className="text-slate-500">Files</dt>
                        <dd className="text-white">{selectedPackage.fileCount}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Updated</dt>
                        <dd className="text-white">{new Date(selectedPackage.updatedAt).toLocaleString()}</dd>
                      </div>
                      {selectedPackage.createdAt ? (
                        <div>
                          <dt className="text-slate-500">Created</dt>
                          <dd className="text-white">{new Date(selectedPackage.createdAt).toLocaleString()}</dd>
                        </div>
                      ) : null}
                    </dl>
                  </div>

                  <div className="overflow-x-auto rounded-[1.5rem] border border-white/8 bg-white/[0.03]">
                    <table className="oc-table">
                      <thead>
                        <tr>
                          {["Role", "Category", "File", "Size", "Updated", "Actions"].map((heading) => (
                            <th key={heading}>{heading}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {selectedPackage.files.map((file) => (
                          <tr key={file.relativePath}>
                            <td className="oc-td-primary">{file.roleKey}</td>
                            <td>{file.category}</td>
                            <td className="font-mono text-xs text-slate-300">{file.relativePath}</td>
                            <td>{formatBytes(file.sizeBytes)}</td>
                            <td>{new Date(file.updatedAt).toLocaleString()}</td>
                            <td>
                              <div className="flex flex-wrap gap-2">
                                <a
                                  href={`/api/artifacts/view?project=${encodeURIComponent(selectedPackage.projectId)}&file=${encodeURIComponent(file.relativePath)}`}
                                  className="oc-btn-ghost"
                                >
                                  Open
                                </a>
                                <a
                                  href={`/api/artifacts/download?project=${encodeURIComponent(selectedPackage.projectId)}&file=${encodeURIComponent(file.relativePath)}`}
                                  className="oc-btn-ghost"
                                >
                                  Download
                                </a>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : (
              <div className="px-6 py-12 text-sm text-slate-400">
                No package selected.
              </div>
            )}
          </section>
        </section>
      </div>
    </main>
  );
}

