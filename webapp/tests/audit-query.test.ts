import { beforeEach, describe, expect, test } from "vitest";

import { recordAuditEvent } from "@/lib/audit/events";
import { countAuditEvents, listRecentAuditEvents } from "@/lib/audit/query";
import { db } from "@/lib/db";

describe("audit query", () => {
  beforeEach(() => {
    db.prepare("DELETE FROM audit_events").run();
  });

  test("returns most recent filtered audit events first", () => {
    recordAuditEvent("audit.test.failure", "Invalid login attempt", "unknown");
    recordAuditEvent("audit.test.success", "User signed in successfully.", "admin");
    recordAuditEvent("audit.test.logout", "User signed out.", "viewer");

    const loginEvents = listRecentAuditEvents({ type: "audit.test.success", actor: "admin", limit: 10 });
    const failureEvents = listRecentAuditEvents({ type: "audit.test.failure", limit: 10 });

    expect(loginEvents).toHaveLength(1);
    expect(loginEvents[0]?.type).toBe("audit.test.success");

    expect(failureEvents).toHaveLength(1);
    expect(failureEvents[0]?.type).toBe("audit.test.failure");
  });

  test("filters by event type", () => {
    recordAuditEvent("audit.test.failure", "Invalid login attempt", "unknown");
    recordAuditEvent("audit.test.success", "User signed in successfully.", "admin");

    const events = listRecentAuditEvents({ type: "audit.test.success", limit: 10 });

    expect(events).toHaveLength(1);
    expect(events[0]?.type).toBe("audit.test.success");
  });

  test("filters by actor text", () => {
    recordAuditEvent("audit.test.success", "User signed in successfully.", "admin");
    recordAuditEvent("audit.test.logout", "User signed out.", "viewer");

    const events = listRecentAuditEvents({ type: "audit.test.logout", actor: "view", limit: 10 });

    expect(events).toHaveLength(1);
    expect(events[0]?.actor).toBe("viewer");
  });

  test("counts events with the same filter set", () => {
    recordAuditEvent("audit.test.success", "User signed in successfully.", "admin");
    recordAuditEvent("audit.test.success", "User signed in successfully.", "admin");
    recordAuditEvent("audit.test.logout", "User signed out.", "viewer");

    expect(countAuditEvents({ type: "audit.test.success" })).toBe(2);
    expect(countAuditEvents({ type: "audit.test.logout", actor: "view" })).toBe(1);
  });

  test("supports offset-based pagination", () => {
    for (let index = 1; index <= 3; index += 1) {
      recordAuditEvent("audit.test.pagination", `Success ${index}`, `admin${index}`);
    }

    const pageOne = listRecentAuditEvents({ type: "audit.test.pagination", limit: 2, offset: 0 });
    const pageTwo = listRecentAuditEvents({ type: "audit.test.pagination", limit: 2, offset: 2 });

    expect(pageOne).toHaveLength(2);
    expect(pageTwo).toHaveLength(1);
    expect(pageOne[0]?.detail).toBe("Success 3");
    expect(pageTwo[0]?.detail).toBe("Success 1");
  });
});
