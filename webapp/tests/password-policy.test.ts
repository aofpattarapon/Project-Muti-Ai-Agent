import { describe, expect, test } from "vitest";

import { validatePasswordPolicy } from "@/lib/security/password-policy";

describe("password policy", () => {
  test("accepts a strong password", () => {
    expect(validatePasswordPolicy("NewAdmin123!").valid).toBe(true);
  });

  test("rejects a password that is too short", () => {
    expect(validatePasswordPolicy("Adm1!xy").valid).toBe(false);
  });

  test("rejects a password without uppercase", () => {
    expect(validatePasswordPolicy("newadmin123!").valid).toBe(false);
  });

  test("rejects a password without lowercase", () => {
    expect(validatePasswordPolicy("NEWADMIN123!").valid).toBe(false);
  });

  test("rejects a password without number", () => {
    expect(validatePasswordPolicy("NewAdmin!!!").valid).toBe(false);
  });

  test("rejects a password without symbol", () => {
    expect(validatePasswordPolicy("NewAdmin123").valid).toBe(false);
  });
});
