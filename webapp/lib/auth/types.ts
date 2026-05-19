export type UserRole = "Admin" | "Operator" | "Viewer";

export type AuthSession = {
  userId: string;
  username: string;
  email: string;
  name: string;
  role: UserRole;
  sessionVersion: number;
};
