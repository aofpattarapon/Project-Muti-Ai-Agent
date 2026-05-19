const DEFAULT_INSECURE_SESSION_SECRET = "dev-session-secret-change-me";
const MIN_SECRET_LENGTH = 16;

export type ResetEmailDeliveryMode = "sink" | "disabled";

export type RuntimeConfig = {
  nodeEnv: "development" | "test" | "production";
  sessionSecret: string;
  trustProxyHeaders: boolean;
  resetEmailDeliveryMode: ResetEmailDeliveryMode;
};

function readNodeEnv(): RuntimeConfig["nodeEnv"] {
  const value = process.env.NODE_ENV?.trim();

  if (value === "production" || value === "test") {
    return value;
  }

  return "development";
}

function readSessionSecret() {
  const value = process.env.SESSION_SECRET?.trim();

  if (!value) {
    throw new Error("Missing required environment variable: SESSION_SECRET");
  }

  if (value === DEFAULT_INSECURE_SESSION_SECRET) {
    throw new Error(
      "Unsafe SESSION_SECRET detected. Replace the default development secret before running this app.",
    );
  }

  if (value.length < MIN_SECRET_LENGTH) {
    throw new Error("SESSION_SECRET must be at least 16 characters long.");
  }

  return value;
}

function readTrustProxyHeaders(nodeEnv: RuntimeConfig["nodeEnv"]) {
  const rawValue = process.env.TRUST_PROXY_HEADERS?.trim().toLowerCase();

  if (rawValue === "true") {
    return true;
  }

  if (rawValue === "false") {
    return false;
  }

  return nodeEnv === "production";
}

function readResetEmailDeliveryMode(nodeEnv: RuntimeConfig["nodeEnv"]): ResetEmailDeliveryMode {
  const rawValue = process.env.RESET_EMAIL_DELIVERY_MODE?.trim().toLowerCase();

  if (rawValue === "sink") {
    return "sink";
  }

  if (rawValue === "disabled") {
    return "disabled";
  }

  return nodeEnv === "production" ? "disabled" : "sink";
}

export function getRuntimeConfig(): RuntimeConfig {
  const nodeEnv = readNodeEnv();

  return {
    nodeEnv,
    sessionSecret: readSessionSecret(),
    trustProxyHeaders: readTrustProxyHeaders(nodeEnv),
    resetEmailDeliveryMode: readResetEmailDeliveryMode(nodeEnv),
  };
}
