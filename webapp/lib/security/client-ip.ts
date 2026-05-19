import { getRuntimeConfig } from "@/lib/config/runtime";

export function getClientIp(request: Request) {
  const { trustProxyHeaders } = getRuntimeConfig();

  if (trustProxyHeaders) {
    const forwardedFor = request.headers.get("x-forwarded-for");

    if (forwardedFor) {
      return forwardedFor.split(",")[0]?.trim() ?? "unknown";
    }

    const realIp = request.headers.get("x-real-ip");

    if (realIp) {
      return realIp.trim() || "unknown";
    }
  }

  return "direct-client";
}
