# LiveKit configuration

Config for the local LiveKit stack in `docker-compose.yml`.

| File | Used by | How |
| --- | --- | --- |
| `livekit.yaml` | `livekit` service | mounted at `/etc/livekit.yaml`, started with `--config /etc/livekit.yaml` |
| `egress.yaml` | `egress` service | reference copy; Compose passes the same body as `EGRESS_CONFIG_BODY` |

## Keys

Neither file holds a secret. Compose reads `LIVEKIT_API_KEY` and
`LIVEKIT_API_SECRET` from the repo-root `.env` and passes them as:

- `LIVEKIT_KEYS="<key>: <secret>"` to the server (the space after the colon is required);
- `LIVEKIT_WEBHOOK_API_KEY=<key>` to the server, which signs webhooks with that key's secret;
- `api_key` / `api_secret` inside `EGRESS_CONFIG_BODY` to Egress;
- `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` to the agent and the API.

Egress gets **no storage credentials**. The API sends an `S3Upload` with every
recording request (endpoint `https://s3.<B2_REGION>.backblazeb2.com`, path-style
addressing), built in `services/api/app/repo/livekit_api.py`.

## Ports

| Port | Protocol | Purpose | Published |
| --- | --- | --- | --- |
| 7880 | TCP | signaling (WebSocket) and the server API | yes |
| 7881 | TCP | WebRTC media over TCP | yes |
| 50000-50019 | UDP | WebRTC media | yes |
| 6379 | TCP | Redis | no |

The UDP range is small on purpose (`rtc.port_range_start/end`): a local demo has
one or two participants plus Egress, and Docker publishes each port separately.

## Networking

- Inside Compose, the agent, Egress and the API reach the server at
  `ws://livekit:7880` on the bridge network.
- A browser on the host connects to `ws://localhost:7880` (`LIVEKIT_PUBLIC_URL`).
  `rtc.enable_loopback_candidate: true` lets the server offer a loopback ICE
  candidate, which the published ports forward into the container;
  `use_external_ip: false` keeps it from advertising a public address.
- Webhooks go to `http://api:8000/api/webhooks/livekit` (`webhook.urls`).

### If the browser cannot join

The agent and Egress connect inside the Compose network, so `make demo` and
`make test` do not depend on browser networking. Browser join is the one path
that crosses from the host into the container. If "Join with microphone"
connects but no audio flows:

1. Confirm the UDP range is published: `docker compose port livekit 50000/udp`.
2. Media falls back to TCP 7881 when UDP is blocked; check it is free on the host.
3. On Docker Desktop for macOS, UDP forwarding into containers depends on the
   VM's port forwarder; if UDP fails there, TCP 7881 still carries the session.
   Keep the container topology as is; it is what the agent and Egress rely on.

## Version pins

`livekit/livekit-server:v1.13.11` and `livekit/egress:v1.15.0`, both multi-arch
(amd64, arm64). Egress v1.15.0 sends S3 request checksums only when required for
non-AWS endpoints, which S3-compatible stores such as B2 need, and records
audio-only room composites through the SDK source without Chrome. The Compose
file keeps upstream's documented `SYS_ADMIN` capability for Egress so switching
to a Chrome-based (video) recording works unchanged.
