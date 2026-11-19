"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Mic } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useCreateSession, useRetentionPolicy, useScripts } from "@/lib/queries";
import { SESSION_CLASSES, retentionLabel } from "@/lib/session-format";
import {
  SESSION_CREATE_DEFAULTS,
  defaultScriptId,
  sessionCreateSchema,
  type SessionCreateValues,
} from "@/lib/session-schema";

const FIRST_RUN_HINT =
  "For a first run keep the support-handoff script, debug class and scripted mode.";

export function SessionCreateForm() {
  const router = useRouter();
  const { data: scripts, isLoading: scriptsLoading } = useScripts();
  const { data: policy } = useRetentionPolicy();
  const create = useCreateSession();
  const form = useForm<SessionCreateValues>({
    resolver: zodResolver(sessionCreateSchema),
    defaultValues: SESSION_CREATE_DEFAULTS,
  });
  // Preselect a bundled script once they load, unless the user already chose one.
  useEffect(() => {
    if (!scripts || form.getValues("script_id")) return;
    const id = defaultScriptId(scripts.items.map((s) => s.id));
    if (id) form.setValue("script_id", id);
  }, [scripts, form]);
  const days = new Map(policy?.classes.map((c) => [c.session_class, c.retain_days]));

  const onSubmit = (values: SessionCreateValues) => {
    create.mutate(values, {
      onSuccess: (manifest) => {
        toast.success(`Session ${manifest.session_id} is recording`, {
          description: "Egress is writing it to B2. The page updates when it is processed.",
        });
        router.push(`/sessions/${manifest.session_id}`);
      },
      onError: (error) => toast.error("Could not start the session", { description: error.message }),
    });
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <Card>
          <CardHeader className="border-b border-border py-4 px-5">
            <CardTitle className="card-title">New session</CardTitle>
          </CardHeader>
          <CardContent className="p-5 space-y-6">
            <FormField
              control={form.control}
              name="script_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Script</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full sm:w-96">
                        <SelectValue
                          placeholder={scriptsLoading ? "Loading scripts..." : "e.g. support-handoff"}
                        />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {scripts?.items.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.title} ({s.line_count} lines, ~{Math.round(s.expected_duration_s)}s)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>{FIRST_RUN_HINT}</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="session_class"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Session class</FormLabel>
                  <FormControl>
                    <RadioGroup
                      onValueChange={field.onChange}
                      value={field.value}
                      className="grid gap-2 sm:grid-cols-2"
                    >
                      {SESSION_CLASSES.map((c) => (
                        <label
                          key={c}
                          className="flex cursor-pointer items-center gap-2 rounded-md border border-border p-3 text-sm"
                        >
                          <RadioGroupItem value={c} />
                          <span className="font-medium capitalize">{c}</span>
                          <span className="ml-auto text-xs text-muted-foreground">
                            {policy ? retentionLabel(days.get(c)) : ""}
                          </span>
                        </label>
                      ))}
                    </RadioGroup>
                  </FormControl>
                  <FormDescription>
                    Decides how long the recording, transcript and evaluation stay in B2.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="mode"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Mode</FormLabel>
                  <FormControl>
                    <Tabs value={field.value} onValueChange={field.onChange}>
                      <TabsList aria-label="Session mode">
                        <TabsTrigger value="scripted">Scripted</TabsTrigger>
                        <TabsTrigger value="interactive">Interactive</TabsTrigger>
                      </TabsList>
                    </Tabs>
                  </FormControl>
                  <FormDescription>
                    Scripted: the test agent speaks and closes the room. Interactive:
                    you join with your microphone from the session page.
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
                  <FormLabel>Label (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. regression check after prompt change" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>
        <Button type="submit" disabled={create.isPending}>
          <Mic className="h-4 w-4" />
          {create.isPending ? "Starting room and Egress..." : "Start session"}
        </Button>
      </form>
    </Form>
  );
}
