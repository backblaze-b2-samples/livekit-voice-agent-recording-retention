import { describe, expect, it } from "vitest";

import {
  SESSION_CREATE_DEFAULTS,
  retentionRunSchema,
  sessionCreateSchema,
  sessionEditSchema,
} from "./session-schema";

describe("session schemas", () => {
  it("requires a script on create (no autofill)", () => {
    expect(sessionCreateSchema.safeParse(SESSION_CREATE_DEFAULTS).success).toBe(false);
    expect(
      sessionCreateSchema.safeParse({ ...SESSION_CREATE_DEFAULTS, script_id: "support-handoff" })
        .success,
    ).toBe(true);
  });

  it("only accepts known classes and modes", () => {
    const base = { ...SESSION_CREATE_DEFAULTS, script_id: "x" };
    expect(sessionCreateSchema.safeParse({ ...base, session_class: "forever" }).success).toBe(false);
    expect(sessionCreateSchema.safeParse({ ...base, mode: "live" }).success).toBe(false);
    expect(sessionEditSchema.safeParse({ session_class: "hold", label: "" }).success).toBe(true);
  });

  it("accepts an empty or ISO as-of date", () => {
    expect(retentionRunSchema.safeParse({ dry_run: true, as_of: "" }).success).toBe(true);
    expect(retentionRunSchema.safeParse({ dry_run: false, as_of: "2026-12-01" }).success).toBe(true);
    expect(retentionRunSchema.safeParse({ dry_run: true, as_of: "12/01/2026" }).success).toBe(false);
  });
});
