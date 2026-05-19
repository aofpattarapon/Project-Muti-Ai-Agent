type AttemptEntry = {
  count: number;
  firstAttemptAt: number;
  blockedUntil: number | null;
};

const WINDOW_MS = 5 * 60 * 1000;
const MAX_FAILURES = 5;
const BLOCK_MS = 10 * 60 * 1000;

const attempts = new Map<string, AttemptEntry>();

function now() {
  return Date.now();
}

function normalizeKey(value: string) {
  return value.trim().toLowerCase();
}

export function clearLoginRateLimitState() {
  attempts.clear();
}

export function getLoginRateLimitKey(usernameOrEmail: string, ipAddress?: string | null) {
  const identity = normalizeKey(usernameOrEmail || "unknown");
  const ip = (ipAddress ?? "unknown").trim() || "unknown";
  return `${identity}::${ip}`;
}

export function isLoginBlocked(key: string) {
  const entry = attempts.get(key);

  if (!entry) {
    return { blocked: false, retryAfterSeconds: 0 };
  }

  if (entry.blockedUntil && entry.blockedUntil > now()) {
    return {
      blocked: true,
      retryAfterSeconds: Math.max(1, Math.ceil((entry.blockedUntil - now()) / 1000)),
    };
  }

  if (entry.blockedUntil && entry.blockedUntil <= now()) {
    attempts.delete(key);
  }

  return { blocked: false, retryAfterSeconds: 0 };
}

export function recordLoginFailure(key: string) {
  const currentTime = now();
  const entry = attempts.get(key);

  if (!entry) {
    attempts.set(key, {
      count: 1,
      firstAttemptAt: currentTime,
      blockedUntil: null,
    });
    return;
  }

  if (entry.blockedUntil && entry.blockedUntil <= currentTime) {
    attempts.set(key, {
      count: 1,
      firstAttemptAt: currentTime,
      blockedUntil: null,
    });
    return;
  }

  if (currentTime - entry.firstAttemptAt > WINDOW_MS) {
    attempts.set(key, {
      count: 1,
      firstAttemptAt: currentTime,
      blockedUntil: null,
    });
    return;
  }

  entry.count += 1;

  if (entry.count >= MAX_FAILURES) {
    entry.blockedUntil = currentTime + BLOCK_MS;
  }

  attempts.set(key, entry);
}

export function recordLoginSuccess(key: string) {
  attempts.delete(key);
}
