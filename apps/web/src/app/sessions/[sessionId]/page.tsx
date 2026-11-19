"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SessionDetailView } from "@/components/sessions/session-detail";

export default function SessionPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title font-mono">{sessionId}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            The session manifest and everything it links to in B2.
          </p>
        </div>
        <Button asChild variant="outline" size="sm" className="h-8">
          <Link href="/sessions">
            <ArrowLeft className="h-3.5 w-3.5" />
            All sessions
          </Link>
        </Button>
      </div>
      <SessionDetailView sessionId={sessionId} />
    </div>
  );
}
