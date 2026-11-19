"use client";

import { Archive, AudioLines, CheckCircle2, HardDrive } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingNotice } from "@/components/common/loading-notice";
import { useArchiveStats } from "@/lib/queries";
import { formatMinutes } from "@/lib/session-format";

export function StatsCards() {
  const { data: stats, isLoading, error, refetch } = useArchiveStats();

  // Surface fetch failures inline rather than rendering zeros: "0 sessions"
  // would lie about the archive when really the API is unreachable.
  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const last = stats?.last_report;
  const cards = [
    { title: "Sessions", value: stats?.total_sessions ?? 0, icon: AudioLines },
    {
      title: "Recorded",
      value: `${formatMinutes(stats?.recorded_seconds ?? 0)} / ${stats?.recorded_bytes_human ?? "0 B"}`,
      icon: HardDrive,
    },
    { title: "Passed evaluations", value: stats?.passed_evaluations ?? 0, icon: CheckCircle2 },
    {
      title: "Last retention run",
      value: last ? `${last.date}: -${last.removed_total}` : "never",
      icon: Archive,
    },
  ];

  return (
    <>
      {isLoading && <LoadingNotice className="mb-3" subject="archive stats" />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card, i) => (
          <Card key={card.title} className={`card-hover animate-fade-in-up stagger-${i + 1}`}>
            <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
              <CardTitle className="text-xs font-semibold text-muted-foreground">
                {card.title}
              </CardTitle>
              <div className="stat-icon-wrap">
                <card.icon className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent className="pb-5 px-4">
              {isLoading ? (
                <Skeleton className="h-8 w-24" />
              ) : (
                <div className="stat-value">{card.value}</div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
