"""Claude Code PreToolUse hook: record the session's permission mode.

Runs right before request_access, so the server can follow the mode:
bypassPermissions skips the approval dialog, dontAsk only allows apps that
were set to "Always allow", every other mode shows the dialog.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as c  # noqa: E402


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        payload = {}
    mode = payload.get("permission_mode") or "unknown"
    c.write_json(c.mode_path(c.claude_ancestor()), {"mode": mode, "at": time.time(),
                                                    "session_id": payload.get("session_id")})


if __name__ == "__main__":
    main()
