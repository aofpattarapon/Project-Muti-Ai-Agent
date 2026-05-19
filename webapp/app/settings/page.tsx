import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth/session";
import { loadAllSettings } from "@/lib/config/env-manager";

import { SettingsClient } from "./SettingsClient";

export default async function SettingsPage() {
  const session = await getSession();

  if (!session) redirect("/login");
  if (session.role !== "Admin") redirect("/dashboard");

  const settings = loadAllSettings();

  return <SettingsClient initialSettings={settings} />;
}
