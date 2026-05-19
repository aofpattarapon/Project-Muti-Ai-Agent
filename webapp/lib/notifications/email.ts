import fs from "node:fs";
import path from "node:path";

import { getRuntimeConfig } from "@/lib/config/runtime";

const dataDir = path.join(process.cwd(), "data");
const emailSinkPath = path.join(dataDir, "email-sink.jsonl");

export type PasswordResetEmailDelivery = {
  kind: "password_reset";
  to: string;
  username: string;
  resetUrl: string;
  expiresAt: string;
  createdAt: string;
};

function ensureDataDirectory() {
  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }
}

export function sendPasswordResetEmail(input: {
  to: string;
  username: string;
  resetUrl: string;
  expiresAt: string;
}) {
  const { resetEmailDeliveryMode } = getRuntimeConfig();

  if (resetEmailDeliveryMode === "disabled") {
    return {
      delivered: false,
      mode: "disabled" as const,
    };
  }

  ensureDataDirectory();

  const entry: PasswordResetEmailDelivery = {
    kind: "password_reset",
    to: input.to,
    username: input.username,
    resetUrl: input.resetUrl,
    expiresAt: input.expiresAt,
    createdAt: new Date().toISOString(),
  };

  fs.appendFileSync(emailSinkPath, `${JSON.stringify(entry)}\n`, "utf8");

  return {
    delivered: true,
    mode: "sink" as const,
  };
}

export function listEmailSinkEntries(): PasswordResetEmailDelivery[] {
  if (!fs.existsSync(emailSinkPath)) {
    return [];
  }

  return fs
    .readFileSync(emailSinkPath, "utf8")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as PasswordResetEmailDelivery);
}

export function clearEmailSink() {
  if (fs.existsSync(emailSinkPath)) {
    fs.unlinkSync(emailSinkPath);
  }
}
