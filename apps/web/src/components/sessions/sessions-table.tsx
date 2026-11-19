"use client";

import { useState } from "react";
import Link from "next/link";
import { AudioLines, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SessionStatusBadge } from "@/components/sessions/session-status-badge";
import { useSessions } from "@/lib/queries";
import {
  SESSION_CLASSES,
  SESSION_STATUSES,
  formatBytes,
  formatDateTime,
  formatDuration,
  formatWer,
} from "@/lib/session-format";

const ALL = "all";
const PAGE_SIZE = 25;

/** The sample's own explorer, scoped to the `sessions/` prefix. */
export function SessionsTable() {
  const [sessionClass, setSessionClass] = useState(ALL);
  const [status, setStatus] = useState(ALL);
  // Cursor stack: the API pages by "older than this session id".
  const [cursors, setCursors] = useState<string[]>([]);
  const cursor = cursors.at(-1);
  const { data, isLoading, isFetching, error, refetch } = useSessions({
    session_class: sessionClass === ALL ? undefined : sessionClass,
    status: status === ALL ? undefined : status,
    cursor,
    limit: PAGE_SIZE,
  });
  const items = data?.items ?? [];

  const filter = (setter: (value: string) => void) => (value: string) => {
    setter(value);
    setCursors([]);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 space-y-0">
        <CardTitle className="card-title">Sessions</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={sessionClass} onValueChange={filter(setSessionClass)}>
            <SelectTrigger className="h-8 w-36" aria-label="Filter by class">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All classes</SelectItem>
              {SESSION_CLASSES.map((c) => (
                <SelectItem key={c} value={c} className="capitalize">
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={status} onValueChange={filter(setStatus)}>
            <SelectTrigger className="h-8 w-36" aria-label="Filter by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {SESSION_STATUSES.map((s) => (
                <SelectItem key={s} value={s} className="capitalize">
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="Refresh sessions"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0" aria-busy={isLoading}>
        {isLoading ? (
          <div className="space-y-2 p-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} title="Couldn't load sessions" onRetry={() => refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={AudioLines}
            title="No sessions match"
            description="Create a session, or clear the filters."
            action={
              <Button asChild size="sm">
                <Link href="/sessions/new">New session</Link>
              </Button>
            }
            className="py-10"
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Session</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Class</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead className="text-right">WER</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((s) => (
                <TableRow key={s.session_id}>
                  <TableCell>
                    <Link
                      href={`/sessions/${s.session_id}`}
                      className="font-mono text-xs hover:underline"
                    >
                      {s.session_id}
                    </Link>
                    <div className="text-xs text-muted-foreground">
                      {s.script_id} · {s.mode}
                      {s.label ? ` · ${s.label}` : ""}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs">{formatDateTime(s.created_at)}</TableCell>
                  <TableCell className="capitalize">{s.session_class}</TableCell>
                  <TableCell>
                    <SessionStatusBadge status={s.status} />
                  </TableCell>
                  <TableCell className="text-right">{formatDuration(s.duration_s)}</TableCell>
                  <TableCell className="text-right">{formatBytes(s.size_bytes)}</TableCell>
                  <TableCell className="text-right">{formatWer(s.wer)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        <div className="flex items-center justify-end gap-2 border-t border-border px-5 py-3">
          <Button
            variant="outline"
            size="sm"
            disabled={cursors.length === 0}
            onClick={() => setCursors((c) => c.slice(0, -1))}
          >
            Newer
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!data?.next_cursor}
            onClick={() => data?.next_cursor && setCursors((c) => [...c, data.next_cursor as string])}
          >
            Older
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
