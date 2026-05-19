import bcrypt from "bcryptjs";

const SALT_ROUNDS = 10;

export async function hashPassword(password: string) {
  return bcrypt.hash(password, SALT_ROUNDS);
}

export function hashPasswordSync(password: string) {
  return bcrypt.hashSync(password, SALT_ROUNDS);
}

export async function verifyPassword(password: string, hashedPassword: string) {
  return bcrypt.compare(password, hashedPassword);
}
