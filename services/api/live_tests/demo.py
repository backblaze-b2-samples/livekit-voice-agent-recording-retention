"""`make demo`: record one scripted session to B2 and print its manifest.

Runs inside the api container against the running stack. Creates a real room,
lets the test agent speak the default script, waits for Egress to upload the
recording to B2 and for post-processing to finish, then prints the manifest.
"""

import json
import sys

from live_tests.session_client import client, create_scripted_session, wait_for_terminal


def main() -> int:
    with client() as http:
        created = create_scripted_session(http, session_class="debug")
        session_id = created["session_id"]
        sys.stdout.write(f"Created {session_id}; waiting for Egress and post-processing...\n")
        detail = wait_for_terminal(http, session_id)
    sys.stdout.write(json.dumps(detail["manifest"], indent=2) + "\n")
    return 0 if detail["manifest"]["status"] == "processed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
