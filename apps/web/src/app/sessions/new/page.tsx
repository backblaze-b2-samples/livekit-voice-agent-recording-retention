import { SessionCreateForm } from "@/components/sessions/session-create-form";

export default function NewSessionPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">New session</h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-prose">
          Creates a LiveKit room, writes the session manifest to B2, dispatches the
          test agent and starts an audio-only Egress that uploads the recording
          straight to your bucket.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2 max-w-3xl">
        <SessionCreateForm />
      </div>
    </div>
  );
}
