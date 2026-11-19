"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useArchiveStats, useRetentionPolicy } from "@/lib/queries";
import { retentionLabel } from "@/lib/session-format";

/** Sessions per retention class and per status, from the manifests in B2. */
export function ClassBreakdown() {
  const { data: stats, isLoading } = useArchiveStats();
  const { data: policy } = useRetentionPolicy();
  const days = new Map(policy?.classes.map((c) => [c.session_class, c.retain_days]));
  const total = Math.max(stats?.total_sessions ?? 0, 1);

  return (
    <Card className="h-full">
      <CardHeader className="border-b border-border px-5 py-4">
        <CardTitle className="card-title">Sessions by class and status</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 p-5">
        {isLoading || !stats ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <>
            <ul className="space-y-3">
              {stats.by_class.map((bucket) => (
                <li key={bucket.name}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-medium capitalize">{bucket.name}</span>
                    <span className="text-muted-foreground">
                      {bucket.count} · {retentionLabel(days.get(bucket.name))}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-muted" aria-hidden="true">
                    <div
                      className="h-1.5 rounded-full bg-primary"
                      style={{ width: `${(bucket.count / total) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
            <dl className="grid grid-cols-5 gap-2 text-center text-xs">
              {stats.by_status.map((bucket) => (
                <div key={bucket.name} className="rounded-md border border-border p-2">
                  <dt className="capitalize text-muted-foreground">{bucket.name}</dt>
                  <dd className="text-base font-semibold">{bucket.count}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </CardContent>
    </Card>
  );
}
