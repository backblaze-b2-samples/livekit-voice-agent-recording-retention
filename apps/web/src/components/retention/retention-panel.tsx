"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Archive } from "lucide-react";
import { toast } from "sonner";
import type { RetentionReport } from "@livekit-voice-agent-recording-retention/shared";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useRetentionPolicy, useRetentionReports, useRunRetention } from "@/lib/queries";
import { formatBytes, formatDateTime, retentionLabel } from "@/lib/session-format";
import { retentionRunSchema, type RetentionRunValues } from "@/lib/session-schema";

function ReportTable({ report }: { report: RetentionReport }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Class</TableHead>
          <TableHead>Policy</TableHead>
          <TableHead className="text-right">Kept</TableHead>
          <TableHead className="text-right">Removed</TableHead>
          <TableHead className="text-right">Already expired</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {report.classes.map((c) => (
          <TableRow key={c.session_class}>
            <TableCell className="capitalize">{c.session_class}</TableCell>
            <TableCell>{retentionLabel(c.retain_days)}</TableCell>
            <TableCell className="text-right">{c.kept.length}</TableCell>
            <TableCell className="text-right">
              {c.removed.length}
              {c.removed.length > 0 && (
                <div className="font-mono text-[10px] text-muted-foreground">
                  {c.removed.map((sid) => (
                    <Link key={sid} href={`/sessions/${sid}`} className="block hover:underline">
                      {sid}
                    </Link>
                  ))}
                </div>
              )}
            </TableCell>
            <TableCell className="text-right">{c.already_expired.length}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export function RetentionPanel() {
  const { data: policy } = useRetentionPolicy();
  const { data: reports, isLoading: reportsLoading } = useRetentionReports();
  const run = useRunRetention();
  const [lastRun, setLastRun] = useState<RetentionReport | null>(null);
  const form = useForm<RetentionRunValues>({
    resolver: zodResolver(retentionRunSchema),
    defaultValues: { dry_run: true, as_of: "" },
  });

  const onSubmit = (values: RetentionRunValues) =>
    run.mutate(
      { dry_run: values.dry_run, as_of: values.as_of || null },
      {
        onSuccess: (report) => {
          setLastRun(report);
          toast.success(report.dry_run ? "Dry run complete" : "Retention applied", {
            description: `${report.removed_total} removed, ${report.kept_total} kept as of ${report.as_of}.`,
          });
        },
        onError: (e) => toast.error("Retention run failed", { description: e.message }),
      },
    );

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle className="card-title">Policy by class</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <ul className="space-y-2 text-sm">
              {policy?.classes.map((c) => (
                <li key={c.session_class} className="flex justify-between">
                  <span className="capitalize font-medium">{c.session_class}</span>
                  <span className="text-muted-foreground">{retentionLabel(c.retain_days)}</span>
                </li>
              )) ?? <Skeleton className="h-24 w-full" />}
            </ul>
            <p className="mt-4 text-xs text-muted-foreground">
              Override with RETENTION_DAYS_DEBUG, RETENTION_DAYS_STANDARD and
              RETENTION_DAYS_TRAINING. Days count from the end of the recording.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle className="card-title">Run retention</CardTitle>
          </CardHeader>
          <CardContent className="p-5">
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="dry_run"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between gap-4">
                      <div>
                        <FormLabel>Dry run</FormLabel>
                        <FormDescription>
                          On: report what would be removed, delete nothing. Off: delete
                          expired media and write reports/&lt;date&gt;.json.
                        </FormDescription>
                      </div>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="as_of"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>As of (optional)</FormLabel>
                      <FormControl>
                        <Input type="date" className="w-48" {...field} />
                      </FormControl>
                      <FormDescription>Defaults to today (UTC).</FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button type="submit" disabled={run.isPending}>
                  <Archive className="h-4 w-4" />
                  {run.isPending ? "Running..." : "Run retention"}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>

      {lastRun && (
        <Card>
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle className="card-title">
              {lastRun.dry_run ? "Dry run" : "Applied run"} as of {lastRun.as_of}:{" "}
              {lastRun.removed_total} removed ({formatBytes(lastRun.removed_bytes)})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ReportTable report={lastRun} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="border-b border-border px-5 py-4">
          <CardTitle className="card-title">Reports in B2</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {reportsLoading ? (
            <Skeleton className="m-5 h-16" />
          ) : !reports || reports.items.length === 0 ? (
            <EmptyState
              icon={Archive}
              title="No applied runs yet"
              description="Turn off dry run to apply retention; each applied run writes reports/<date>.json."
              className="py-10"
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Generated</TableHead>
                  <TableHead className="text-right">Kept</TableHead>
                  <TableHead className="text-right">Removed</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.items.map((r) => (
                  <TableRow key={r.key}>
                    <TableCell>{r.date}</TableCell>
                    <TableCell className="font-mono text-xs">{r.key}</TableCell>
                    <TableCell className="text-xs">{formatDateTime(r.generated_at)}</TableCell>
                    <TableCell className="text-right">{r.kept_total}</TableCell>
                    <TableCell className="text-right">{r.removed_total}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
