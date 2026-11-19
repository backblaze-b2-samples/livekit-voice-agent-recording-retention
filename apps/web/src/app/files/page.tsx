import Link from "next/link";
import { Mic } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FileBrowser } from "@/components/files/file-browser";

export default function FilesPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Files</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            Everything in the bucket: session recordings, manifests,
            transcripts, webhook evidence and retention reports. Click a file to
            preview it.
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
        <FileBrowser />
      </div>
    </div>
  );
}
