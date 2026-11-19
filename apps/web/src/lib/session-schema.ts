import { z } from "zod";

import { SESSION_CLASSES, SESSION_MODES } from "@/lib/session-format";

/**
 * Validation for the session create and edit forms. Kept outside the
 * components so the rules are unit-tested without rendering a form. The API
 * validates the same fields again (Pydantic), so these are UX, not security.
 */
export const sessionCreateSchema = z.object({
  script_id: z.string().min(1, "Choose a script"),
  session_class: z.enum(SESSION_CLASSES),
  mode: z.enum(SESSION_MODES),
  label: z.string().max(120, "Label must be 120 characters or fewer"),
});

export type SessionCreateValues = z.infer<typeof sessionCreateSchema>;

/** Empty on purpose: the form guides via placeholder text, it does not autofill. */
export const SESSION_CREATE_DEFAULTS: SessionCreateValues = {
  script_id: "",
  session_class: "debug",
  mode: "scripted",
  label: "",
};

export const sessionEditSchema = z.object({
  session_class: z.enum(SESSION_CLASSES),
  label: z.string().max(120, "Label must be 120 characters or fewer"),
});

export type SessionEditValues = z.infer<typeof sessionEditSchema>;

export const retentionRunSchema = z.object({
  dry_run: z.boolean(),
  as_of: z
    .string()
    .regex(/^(\d{4}-\d{2}-\d{2})?$/, "Use YYYY-MM-DD, or leave empty for today"),
});

export type RetentionRunValues = z.infer<typeof retentionRunSchema>;
