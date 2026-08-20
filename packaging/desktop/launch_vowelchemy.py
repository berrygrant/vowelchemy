"""Desktop entry point for the packaged (PyInstaller) Vowelchemy app.

Double-clicking the built app:

1. starts the FastAPI server on a free localhost port (background thread),
2. opens the app in the default browser once the server answers,
3. shows a small status window — closing it stops Vowelchemy.

The window is the quit story: without it, a windowed (no-console) build would
leave the server running invisibly after the browser closes.  When tkinter is
unavailable (some Linux builds), we fall back to console mode and Ctrl+C.
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request
import webbrowser


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_up(url: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
        except OSError:
            time.sleep(0.25)
        else:
            return True
    return False


def _status_window(url: str) -> None:
    """Block in a tiny Tk window; closing it exits the process (and server)."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Vowelchemy")
    root.resizable(False, False)
    frame = tk.Frame(root, padx=18, pady=14)
    frame.pack()
    tk.Label(frame, text="🧪 Vowelchemy is running", font=("TkDefaultFont", 13, "bold")).pack(
        anchor="w"
    )
    tk.Label(frame, text=f"Address: {url}").pack(anchor="w", pady=(4, 10))
    row = tk.Frame(frame)
    row.pack(anchor="w")
    tk.Button(row, text="Open in browser", command=lambda: webbrowser.open(url)).pack(
        side="left", padx=(0, 8)
    )
    tk.Button(row, text="Quit Vowelchemy", command=root.destroy).pack(side="left")
    tk.Label(
        frame,
        text="Keep this window around while you work.\nClosing it stops Vowelchemy.",
        justify="left",
        fg="#555555",
    ).pack(anchor="w", pady=(10, 0))
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


def main() -> int:
    import uvicorn

    from vowelchemy.api import app

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    if not _wait_until_up(url):
        print("Vowelchemy's server did not start — please report this.", flush=True)
        return 1
    webbrowser.open(url)
    try:
        _status_window(url)
    except Exception:
        # No display / no Tk: stay alive in console mode instead.
        print(f"Vowelchemy is running at {url}  (Ctrl+C to stop)", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
