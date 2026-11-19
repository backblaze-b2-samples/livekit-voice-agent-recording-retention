"use client";

import type { SessionDetail } from "@livekit-voice-agent-recording-retention/shared";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatWer } from "@/lib/session-format";

/** Transcript, evaluation, webhook evidence and the raw manifest, as stored in B2. */
export function SessionEvidence({ detail }: { detail: SessionDetail }) {
  const { manifest, transcript, evaluation, webhooks } = detail;
  return (
    <Card>
      <CardHeader className="border-b border-border px-5 py-4">
        <CardTitle className="card-title">What is in B2</CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        <Tabs defaultValue="transcript">
          <TabsList>
            <TabsTrigger value="transcript">Transcript</TabsTrigger>
            <TabsTrigger value="evaluation">Evaluation</TabsTrigger>
            <TabsTrigger value="webhooks">Webhooks ({webhooks.length})</TabsTrigger>
            <TabsTrigger value="manifest">Manifest</TabsTrigger>
          </TabsList>
          <TabsContent value="transcript" className="pt-4 text-sm">
            {transcript ? (
              <>
                <p className="mb-3 text-xs text-muted-foreground">
                  {transcript.model} on {transcript.device}, language {transcript.language ?? "?"}
                </p>
                <ul className="space-y-1">
                  {transcript.segments.map((s, i) => (
                    <li key={i}>
                      <span className="mr-2 font-mono text-xs text-muted-foreground">
                        {s.start.toFixed(1)}s
                      </span>
                      {s.text}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-muted-foreground">No transcript yet.</p>
            )}
          </TabsContent>
          <TabsContent value="evaluation" className="pt-4 text-sm">
            {evaluation ? (
              <div className="space-y-3">
                <p>
                  <strong>{evaluation.passed ? "Passed" : "Failed"}</strong>: WER{" "}
                  {formatWer(evaluation.wer)} (max {formatWer(evaluation.max_wer)}),{" "}
                  {evaluation.phrases_found.length}/{evaluation.expected_phrases.length} expected
                  phrases heard.
                </p>
                {evaluation.phrases_missing.length > 0 && (
                  <p className="text-muted-foreground">
                    Missing: {evaluation.phrases_missing.join(", ")}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">Reference: {evaluation.reference_text}</p>
              </div>
            ) : (
              <p className="text-muted-foreground">No evaluation yet.</p>
            )}
          </TabsContent>
          <TabsContent value="webhooks" className="pt-4 text-sm">
            {webhooks.length === 0 ? (
              <p className="text-muted-foreground">No verified webhooks stored yet.</p>
            ) : (
              <ul className="space-y-1 font-mono text-xs">
                {webhooks.map((w) => (
                  <li key={w.key}>
                    {w.event} <span className="text-muted-foreground">{w.event_id}</span>
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>
          <TabsContent value="manifest" className="pt-4">
            <pre className="max-h-96 overflow-auto rounded-md bg-muted p-3 text-xs">
              {JSON.stringify(manifest, null, 2)}
            </pre>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
