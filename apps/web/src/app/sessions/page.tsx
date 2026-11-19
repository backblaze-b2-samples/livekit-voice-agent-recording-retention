import Link from "next/link";
import { Mic } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SessionsTable } from "@/components/sessions/sessions-table";

export default function SessionsPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Sessions</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Every session under <code>sessions/</code> in the bucket, read from its
            manifest. Open one to play the recording and see its transcript,
            evaluation and webhook evidence.
          </p>
        </div>
        <Button asChild size="sm" className="h-8 shrink-0">
          <Link href="/sessions/new">
            <Mic aria-hidden="true" className="h-3.5 w-3.5" />
            New session
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <SessionsTable />
      </div>
    </div>
  );
}
