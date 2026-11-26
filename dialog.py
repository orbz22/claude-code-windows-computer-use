"""Approval dialog: Allow for this session / Always allow / Deny.

Uses Tkinter for custom buttons. Falls back to a Yes/No MessageBox
(Yes = allow for this session) when Tkinter is unavailable.
"""

from __future__ import annotations

SESSION, ALWAYS, DENY = "session", "always", "deny"

BG = "#0F172A"
PANEL = "#111C33"
FG = "#E2E8F0"
MUTED = "#94A3B8"
ACCENT = "#F97316"
CYAN = "#38BDF8"
WARN = "#FBBF24"


def ask_approval(title: str, intro: str, apps: list[tuple[str, str, str | None]],
                 extras: list[str], hidden_count: int, reason: str) -> str:
    """apps: (label, tier text, warning or None). Returns SESSION, ALWAYS or DENY."""
    try:
        return _tk_dialog(title, intro, apps, extras, hidden_count, reason)
    except Exception:
        import winapi as w

        lines = [intro, ""]
        for label, tier, warn in apps:
            lines.append(f"   •  {label}  —  {tier}")
            if warn:
                lines.append(f"         ⚠  {warn}")
        if extras:
            lines += ["", "Extra permissions: " + ", ".join(extras)]
        lines += ["", f"{hidden_count} other app(s) will be hidden while Claude works.",
                  "", f"Reason: {reason}", "", "Yes = Allow for this session        No = Deny"]
        return SESSION if w.ask_yes_no(title, "\n".join(lines)) else DENY


def _tk_dialog(title, intro, apps, extras, hidden_count, reason) -> str:
    import tkinter as tk
    from tkinter import font as tkfont

    result = {"choice": DENY}
    root = tk.Tk()
    root.withdraw()
    root.title(title)
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    try:
        import os

        icon = tk.PhotoImage(file=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "assets", "logo-128.png"))
        root.iconphoto(True, icon)
    except tk.TclError:
        pass

    base = tkfont.Font(family="Segoe UI", size=10)
    bold = tkfont.Font(family="Segoe UI Semibold", size=11)
    small = tkfont.Font(family="Segoe UI", size=9)

    body = tk.Frame(root, bg=BG, padx=22, pady=18)
    body.pack(fill="both", expand=True)

    tk.Label(body, text="Claude Code — computer use", font=bold, fg=FG, bg=BG,
             anchor="w").pack(fill="x")
    tk.Label(body, text=intro, font=base, fg=MUTED, bg=BG, anchor="w",
             justify="left").pack(fill="x", pady=(2, 12))

    panel = tk.Frame(body, bg=PANEL, padx=14, pady=10)
    panel.pack(fill="x")
    for label, tier, warn in apps:
        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="●", font=small, fg=CYAN, bg=PANEL).pack(side="left", padx=(0, 8))
        tk.Label(row, text=label, font=base, fg=FG, bg=PANEL, anchor="w").pack(side="left")
        tk.Label(row, text=tier, font=small, fg=ACCENT, bg=PANEL, anchor="e").pack(side="right")
        if warn:
            tk.Label(panel, text=f"⚠  {warn}", font=small, fg=WARN, bg=PANEL, anchor="w"
                     ).pack(fill="x", padx=(20, 0))

    meta = []
    if extras:
        meta.append("Extra permissions: " + ", ".join(extras))
    meta.append(f"{hidden_count} other app(s) will be hidden while Claude works.")
    meta.append(f"Reason: {reason}")
    meta.append("Press Esc anytime to stop Claude.")
    tk.Label(body, text="\n".join(meta), font=small, fg=MUTED, bg=BG, anchor="w",
             justify="left", wraplength=460).pack(fill="x", pady=(12, 14))

    buttons = tk.Frame(body, bg=BG)
    buttons.pack(fill="x")

    def choose(choice):
        result["choice"] = choice
        root.destroy()

    def button(text, choice, primary=False):
        b = tk.Button(buttons, text=text, font=base, relief="flat", cursor="hand2",
                      padx=14, pady=6, bd=0, highlightthickness=0,
                      bg=ACCENT if primary else PANEL, fg="#FFFFFF" if primary else FG,
                      activebackground="#EA580C" if primary else "#1E293B",
                      activeforeground="#FFFFFF", command=lambda: choose(choice))
        b.pack(side="right", padx=(8, 0))
        return b

    deny = button("Deny", DENY)
    button("Always allow", ALWAYS)
    button("Allow for this session", SESSION, primary=True)

    root.protocol("WM_DELETE_WINDOW", lambda: choose(DENY))
    deny.focus_set()  # Enter on the default focus never grants access

    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"{max(w, 500)}x{h}+{x}+{y}")
    root.deiconify()
    root.lift()
    root.focus_force()
    root.after(200, lambda: root.attributes("-topmost", True))
    root.mainloop()
    return result["choice"]
