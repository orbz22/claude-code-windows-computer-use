# claude-code-windows-computer-use

Unofficial Windows port of Claude Code's [computer use](https://code.claude.com/docs/en/computer-use),
which in the CLI only runs on macOS. It is a standalone MCP server that gives Claude Code
screenshots, mouse and keyboard control of your Windows desktop, with the same guardrails
as the original.

> Not affiliated with or endorsed by Anthropic. This server controls your real desktop.
> Read [Safety](#safety) before using it.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- Claude Code

## Install

```powershell
git clone https://github.com/orbz22/claude-code-windows-computer-use.git
cd claude-code-windows-computer-use
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Register the server. Claude Code reserves the name `computer-use`, so use another name:

```powershell
claude mcp add --scope user windows-computer-use -- "$PWD\.venv\Scripts\python.exe" "$PWD\server.py"
```

Add a Stop hook to `~/.claude/settings.json`. It restores hidden apps when Claude's turn ends.
Replace `<repo>` with the full path to your clone, using forward slashes:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"<repo>/.venv/Scripts/python.exe\" \"<repo>/turn_end.py\"",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Restart Claude Code, then run `/mcp` and check that `windows-computer-use` is connected.
To turn it off in one project, disable it in `/mcp`.

## Usage

Ask Claude for something that needs the GUI:

```text
Open Calculator, compute 12 × 34 and take a screenshot of the result.
```

The first time Claude needs an app in a session, a topmost Windows dialog lists the apps,
their permission level and any warnings. **Yes** means Allow for this session, **No** means Deny.

## How it mirrors the macOS version

| macOS original | This server |
| :- | :- |
| Per-app approval for each session | `request_access` opens a Windows dialog |
| Browsers and trading apps view-only, terminals and IDEs click-only, other apps full control | Same tiers, enforced on every click and keystroke |
| Warnings: shell access, any file, system settings | Same warnings in the dialog |
| Approve Finder to use the desktop and Dock | Approve File Explorer to use the desktop and taskbar. Win-key shortcuts need it too |
| Other apps hidden, restored at turn end | Other apps are minimized, then restored by the Stop hook, after 90 s idle, or on exit |
| Terminal excluded from screenshots | The Claude Code terminal is blacked out (z-order aware) and cannot be clicked or typed into |
| Screenshots downscaled automatically | About 1.22 MP budget (1920x1080 becomes 1473x828). `zoom` shows native resolution |
| Esc stops Claude from anywhere, and the key press is consumed | A low-level keyboard hook swallows a physical Esc and aborts until the next turn |
| Notifications | "Claude is using your computer · press Esc to stop", then "done" |
| One session at a time | Lock file in `%LOCALAPPDATA%\claude-win-computer-use`, held until the session exits |

Tools: `request_access`, `list_apps`, `screenshot`, `zoom`, `left_click`, `right_click`,
`middle_click`, `double_click`, `triple_click`, `mouse_move`, `left_click_drag`, `scroll`,
`type`, `key`, `hold_key`, `wait`, `cursor_position`, `open_application`,
`switch_application`, `read_clipboard`, `write_clipboard`.

## Safety

- Input goes to your real desktop. Nothing is sandboxed.
- On-screen text, such as web pages, emails or documents, can carry prompt injection.
  Approve only the apps the task needs, and watch while Claude works.
- Press **Esc** at any time to stop.
- Apps restore their previous state on launch. Windows 11 Notepad, for example, reopens your
  unsaved tabs, so Claude's typing can land in an existing document.
- Approve terminals, IDEs, File Explorer and Settings only when the task really needs them.

## Limits

- Windows (UIPI) blocks a normal process from sending input to elevated (admin) windows.
  Run Claude Code as admin if you need that.
- The approval prompt is a native dialog, not a terminal prompt. MCP elicitation is not used,
  because the client agent could answer it on its own.
- "Hidden" apps are minimized, not hidden, so they stay on the taskbar and nothing is lost
  if the server crashes.
- Multi-monitor: `screenshot(display=N)` selects the monitor. The default is the primary one.

## Files

| File | Role |
| :- | :- |
| `server.py` | MCP server: tools, policy, screenshots |
| `winapi.py` | ctypes wrappers: windows, SendInput, Esc hook, clipboard, dialog |
| `common.py` | State shared with the Stop hook: lock, notifications, restore |
| `turn_end.py` | Stop hook: restores hidden apps when the turn ends |

## License

MIT
