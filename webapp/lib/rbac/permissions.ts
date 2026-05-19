import type { UserRole } from "@/data/seed-users";

export const roleSections: Record<UserRole, string[]> = {
  Admin: [
    "System overview",
    "Team activity",
    "Audit queue",
    "Agent control",
    "Back-office config",
    "Admin controls",
  ],
  Operator: ["Work queue", "Assigned tasks", "Recent activity"],
  Viewer: ["Overview", "Read-only summary"],
};

export function canViewAdminControls(role: UserRole) {
  return role === "Admin";
}
