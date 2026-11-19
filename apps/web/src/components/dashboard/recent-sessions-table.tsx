"use client";

import Link from "next/link";
import { AudioLines } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SessionStatusBadge } from "@/components/sessions/session-status-badge";
import { useArchiveStats } from "@/lib/queries";
import { formatDuration, formatWer } from "@/lib/session-format";

export function RecentSessionsTable() {
  const { data: stats, isLoading } = useArchiveStats();
  const sessions = stats?.recent_sessions ?? [];

  return (
    <Card className="h-full">
      <CardHeader className="border-b border-border px-5 py-4">
        <CardTitle className="card-title">Recent sessions</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="space-y-2 p-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <EmptyState
            icon={AudioLines}
            title="No sessions yet"
            description="Create a scripted session and Egress will record it to B2."
            className="py-10"
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Session</TableHead>
                <TableHead>Class</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead className="text-right">WER</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((s) => (
                <TableRow key={s.session_id}>
                  <TableCell className="font-mono text-xs">
                    <Link href={`/sessions/${s.session_id}`} className="hover:underline">
                      {s.session_id}
                    </Link>
                  </TableCell>
                  <TableCell className="capitalize">{s.session_class}</TableCell>
                  <TableCell>
                    <SessionStatusBadge status={s.status} />
                  </TableCell>
                  <TableCell className="text-right">{formatDuration(s.duration_s)}</TableCell>
                  <TableCell className="text-right">{formatWer(s.wer)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
