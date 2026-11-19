"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import type { SessionManifest } from "@livekit-voice-agent-recording-retention/shared";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useUpdateSession } from "@/lib/queries";
import { SESSION_CLASSES } from "@/lib/session-format";
import { sessionEditSchema, type SessionEditValues } from "@/lib/session-schema";

/** Opens pre-filled from the manifest; saving recomputes `retain_until`. */
export function SessionEditForm({ manifest }: { manifest: SessionManifest }) {
  const update = useUpdateSession(manifest.session_id);
  const expired = manifest.status === "expired";
  const form = useForm<SessionEditValues>({
    resolver: zodResolver(sessionEditSchema),
    values: {
      session_class: manifest.session_class as SessionEditValues["session_class"],
      label: manifest.label,
    },
  });

  const onSubmit = (values: SessionEditValues) => {
    update.mutate(expired ? { label: values.label } : values, {
      onSuccess: () => toast.success("Session updated"),
      onError: (error) => toast.error("Update failed", { description: error.message }),
    });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="session_class"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Class</FormLabel>
              <FormControl>
                <RadioGroup
                  onValueChange={field.onChange}
                  value={field.value}
                  className="flex flex-wrap gap-4"
                  disabled={expired}
                >
                  {SESSION_CLASSES.map((c) => (
                    <label key={c} className="flex items-center gap-2 text-sm capitalize">
                      <RadioGroupItem value={c} />
                      {c}
                    </label>
                  ))}
                </RadioGroup>
              </FormControl>
              <FormDescription>
                {expired
                  ? "This session's media is already removed; its class is final."
                  : "Changing the class recomputes how long the session is kept."}
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="label"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Label</FormLabel>
              <FormControl>
                <Input placeholder="e.g. baseline before prompt change" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit" size="sm" disabled={update.isPending}>
          {update.isPending ? "Saving..." : "Save"}
        </Button>
      </form>
    </Form>
  );
}
