import { RetentionPanel } from "@/components/retention/retention-panel";

export default function RetentionPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Retention</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-prose">
          Keep or remove each session by its class. Removal deletes every version of
          the recording, transcript and evaluation; the manifest stays as an
          <code> expired</code> record.
        </p>
      </div>
      <RetentionPanel />
    </div>
  );
}
