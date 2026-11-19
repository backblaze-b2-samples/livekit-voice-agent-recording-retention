"use client";

import { useEffect, useRef, useState } from "react";
import type { Room } from "livekit-client";
import { Mic, PhoneOff } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useJoinToken } from "@/lib/queries";

type JoinState = "idle" | "connecting" | "connected";

/**
 * Join an interactive session's room with the browser microphone.
 *
 * The API mints a short-lived token for this room only; `livekit-client`
 * (Apache-2.0) connects to the local LiveKit server on ws://localhost:7880.
 * Egress records the room, so your voice and the agent's land in the same
 * recording. Leaving the room lets the agent close it, which ends the Egress.
 */
export function JoinPanel({ sessionId }: { sessionId: string }) {
  const token = useJoinToken(sessionId);
  const [state, setState] = useState<JoinState>("idle");
  const roomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLDivElement>(null);

  useEffect(() => () => void roomRef.current?.disconnect(), []);

  const join = async () => {
    setState("connecting");
    try {
      const identity = `browser-${Math.random().toString(16).slice(2, 8)}`;
      const grant = await token.mutateAsync(identity);
      // Loaded on demand: the SDK touches browser-only APIs.
      const { Room, RoomEvent, Track } = await import("livekit-client");
      const room = new Room();
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio && audioRef.current) {
          audioRef.current.appendChild(track.attach());
        }
      });
      room.on(RoomEvent.Disconnected, () => setState("idle"));
      await room.connect(grant.url, grant.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      roomRef.current = room;
      setState("connected");
    } catch (error) {
      setState("idle");
      toast.error("Could not join the room", {
        description: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const leave = async () => {
    await roomRef.current?.disconnect();
    roomRef.current = null;
    setState("idle");
  };

  return (
    <Card>
      <CardHeader className="border-b border-border px-5 py-4">
        <CardTitle className="card-title">Join this room</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-5 text-sm">
        <p className="text-muted-foreground">
          Interactive session: the agent greets you and reads its script. Talk back,
          then leave; the room closes and Egress finishes the upload to B2.
        </p>
        {state === "connected" ? (
          <Button variant="destructive" onClick={leave}>
            <PhoneOff className="h-4 w-4" />
            Leave room
          </Button>
        ) : (
          <Button onClick={join} disabled={state === "connecting"}>
            <Mic className="h-4 w-4" />
            {state === "connecting" ? "Connecting..." : "Join with microphone"}
          </Button>
        )}
        <div ref={audioRef} hidden />
      </CardContent>
    </Card>
  );
}
