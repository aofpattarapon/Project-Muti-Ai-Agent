import crypto from "node:crypto";

import { getRuntimeConfig } from "@/lib/config/runtime";

function getSecret() {
  return getRuntimeConfig().sessionSecret;
}

export function signSessionValue(payload: string) {
  const signature = crypto
    .createHmac("sha256", getSecret())
    .update(payload)
    .digest("base64url");

  return `${payload}.${signature}`;
}

export function verifySignedSessionValue(value: string) {
  const lastDot = value.lastIndexOf(".");

  if (lastDot <= 0) {
    return null;
  }

  const payload = value.slice(0, lastDot);
  const signature = value.slice(lastDot + 1);

  const expectedSignature = crypto
    .createHmac("sha256", getSecret())
    .update(payload)
    .digest("base64url");

  if (signature !== expectedSignature) {
    return null;
  }

  return payload;
}
