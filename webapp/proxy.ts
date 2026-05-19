import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "maa_session";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (
    !pathname.startsWith("/dashboard") &&
    !pathname.startsWith("/audit") &&
    !pathname.startsWith("/users")
  ) {
    return NextResponse.next();
  }

  const session = request.cookies.get(SESSION_COOKIE)?.value;

  if (!session) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/audit/:path*", "/users/:path*"],
};
