"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { JoinPanel } from "@/components/sessions/join-panel";
import { SessionEditForm } from "@/components/sessions/session-edit-form";
import { SessionEvidence } from "@/components/sessions/session-evidence";
import { SessionStatusBadge } from "@/components/sessions/session-status-badge";
import { previewHref } from "@/lib/preview-deep-link";
import { useDeleteSession, useReprocessSession, useSession } from "@/lib/queries";
import {
  formatBytes,
  formatDateTime,
  formatDuration,
  formatWer,
  retentionLabel,
} from "@/lib/session-format";

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium break-all">{value}</dd>
    </div>
  );
}

export function SessionDetailView({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const { data, isLoading, error, refetch } = useSession(sessionId);
  const remove = useDeleteSession();
  const reprocess = useReprocessSession(sessionId);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (error || !data) {
    return <ErrorState error={error} title="Couldn't load this session" onRetry={() => refetch()} />;
  }
  const m = data.manifest;
  const canReprocess = m.status === "recorded" || m.status === "processed" || m.status === "failed";

  const onDelete = () =>
    remove.mutate(sessionId, {
      onSuccess: () => {
        toast.success(`Deleted ${sessionId}`, { description: "Every version under its prefix is gone." });
        router.push("/sessions");
      },
      onError: (e) => toast.error("Delete failed", { description: e.message }),
    });

  const onReprocess = () =>
    reprocess.mutate(undefined, {
      onSuccess: () => toast.success("Reprocessing", { description: "Checksum, transcription and evaluation run again." }),
      onError: (e) => toast.error("Could not reprocess", { description: e.message }),
    });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <SessionStatusBadge status={m.status} />
        <span className="text-sm text-muted-foreground">
          {m.script_id} · {m.mode} · created {formatDateTime(m.created_at)}
        </span>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm" onClick={onReprocess} disabled={!canReprocess || reprocess.isPending}>
            <RefreshCw className="h-3.5 w-3.5" />
            Reprocess
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm" disabled={remove.isPending}>
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete {sessionId}?</AlertDialogTitle>
                <AlertDialogDescription>
                  Removes every version of every object under this session&apos;s prefix in
                  B2: recording, manifest, transcript, evaluation and webhook evidence. This
                  cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={onDelete}>Delete session</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {m.error && (
        <p role="alert" className="rounded-md border border-destructive/40 p-3 text-sm text-destructive">
          {m.error}
        </p>
      )}

      {m.mode === "interactive" && m.status === "recording" && <JoinPanel sessionId={sessionId} />}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle className="card-title">Recording</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 p-5">
            {data.recording_url ? (
              <audio controls preload="none" src={data.recording_url} className="w-full">
                <track kind="captions" />
              </audio>
            ) : (
              <p className="text-sm text-muted-foreground">
                {m.status === "recording"
                  ? "Recording in progress. Egress uploads the file to B2 when the room closes."
                  : m.status === "expired"
                    ? "Removed by retention. The manifest stays as a record."
                    : "No recording in B2."}
              </p>
            )}
            <dl className="grid grid-cols-2 gap-3">
              <Fact label="Duration" value={formatDuration(m.recording.duration_s)} />
              <Fact label="Size" value={formatBytes(m.recording.size_bytes)} />
              <Fact label="Egress" value={m.egress.status ?? "-"} />
              <Fact label="WER" value={formatWer(m.evaluation?.wer)} />
              <Fact label="Key" value={<Link href={previewHref(m.recording.key)} className="font-mono text-xs hover:underline">{m.recording.key}</Link>} />
              <Fact label="SHA-256" value={<span className="font-mono text-xs">{m.recording.sha256 ?? "-"}</span>} />
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle className="card-title">Class and retention</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 p-5">
            <dl className="grid grid-cols-2 gap-3">
              <Fact label="Policy" value={`${m.session_class}: ${retentionLabel(m.retention.retain_days)}`} />
              <Fact label="Retain until" value={formatDateTime(m.retention.retain_until)} />
              <Fact label="Removed at" value={formatDateTime(m.retention.removed_at)} />
            </dl>
            <SessionEditForm manifest={m} />
          </CardContent>
        </Card>
      </div>

      <SessionEvidence detail={data} />
    </div>
  );
}
