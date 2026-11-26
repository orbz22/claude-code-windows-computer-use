"""Claude Code Stop hook: the turn is over, so restore hidden apps.

Only touches the computer-use server that belongs to the same Claude Code
process as this hook, so other sessions are unaffected.
"""

from __future__ import annotations

import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as c  # noqa: E402


def main() -> None:
    try:
        sys.stdin.read()  # hook payload; not needed
    except Exception:
        pass
    mine = c.claude_ancestor()
    now = time.time()
    for path in glob.glob(os.path.join(c.STATE_DIR, "state-*.json")):
        data = c.read_json(path)
        if not data:
            continue
        if not c.process_alive(data.get("pid", 0), data.get("create_time")):
            c.restore_windows(data.get("hidden", []))
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        if mine is not None and data.get("claude_pid") not in (None, mine):
            continue
        was_active = data.get("active") or data.get("hidden")
        if data.get("hidden"):
            c.restore_windows(data["hidden"])
        data.update(hidden=[], active=False, turn_end_at=now)
        c.write_json(path, data)
        if was_active:
            c.notify("Claude is done using your computer.")


if __name__ == "__main__":
    main()
