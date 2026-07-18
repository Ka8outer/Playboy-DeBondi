# playboy_convert_gui.py
# A simple point-and-click front end for playboy_convert.py.
#
# It does not do any conversion itself: it builds the right command line and
# runs playboy_convert.py, streaming that script's progress into the log
# window. That means the GUI reuses everything the engine already does -
# subprocess isolation for batches, per-page error handling, gatefold
# detection - and the heavy 32-bit DLL work stays in a separate process.
#
# Launch it with 32-bit Python 3.10 (the same one the engine needs):
#   py -3.10-32 playboy_convert_gui.py
# or just double-click "Playboy Converter.bat".

import os
import sys
import queue
import threading
import subprocess

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(SCRIPT_DIR, "playboy_convert.py")
DLL_NAME = "BondiReader.DJVU.dll"


def resolve_converter_python():
    """Return the path to a 32-bit Python interpreter to run the engine.

    The engine must run under 32-bit Python (the Bondi DLL is 32-bit). If we
    are already running 32-bit, just use ourselves. Otherwise ask the Windows
    'py' launcher for a 32-bit 3.10, so double-clicking under a 64-bit Python
    still works.
    """
    if sys.maxsize <= 2 ** 32:
        return sys.executable
    for launcher_args in (["py", "-3.10-32"], ["py", "-3-32"]):
        try:
            out = subprocess.run(
                launcher_args + ["-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=15,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:
            pass
    return None


def find_dll_dir():
    """Locate the folder holding BondiReader.DJVU.dll, or None if missing."""
    for d in (os.path.join(SCRIPT_DIR, "dlls"), SCRIPT_DIR):
        if os.path.exists(os.path.join(d, DLL_NAME)):
            return d
    return None


class ConverterGUI:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.log_queue = queue.Queue()
        self.converter_python = resolve_converter_python()

        root.title("Playboy: Cover to Cover - Converter")
        root.minsize(640, 560)

        pad = {"padx": 10, "pady": 6}
        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        row = 0

        # --- What to convert -------------------------------------------------
        ttk.Label(main, text="What do you want to convert?",
                  font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", **pad)
        row += 1

        self.mode = tk.StringVar(value="folder")
        mode_frame = ttk.Frame(main)
        mode_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=10)
        ttk.Radiobutton(mode_frame, text="A whole folder of issues (batch)",
                        variable=self.mode, value="folder",
                        command=self._clear_path).pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="A single .djvu issue",
                        variable=self.mode, value="file",
                        command=self._clear_path).pack(anchor="w")
        row += 1

        # --- Source path -----------------------------------------------------
        ttk.Label(main, text="Source:").grid(row=row, column=0, sticky="w", **pad)
        self.path_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.path_var).grid(
            row=row, column=1, sticky="ew", pady=6)
        ttk.Button(main, text="Browse...", command=self._browse_source).grid(
            row=row, column=2, padx=10)
        row += 1

        # --- Output folder ---------------------------------------------------
        ttk.Label(main, text="Save to:").grid(row=row, column=0, sticky="w", **pad)
        self.output_var = tk.StringVar(value=os.path.join(SCRIPT_DIR, "output"))
        ttk.Entry(main, textvariable=self.output_var).grid(
            row=row, column=1, sticky="ew", pady=6)
        ttk.Button(main, text="Browse...", command=self._browse_output).grid(
            row=row, column=2, padx=10)
        row += 1

        # --- Format ----------------------------------------------------------
        ttk.Label(main, text="Format:").grid(row=row, column=0, sticky="w", **pad)
        self.format = tk.StringVar(value="cbz")
        fmt_frame = ttk.Frame(main)
        fmt_frame.grid(row=row, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(fmt_frame, text="CBZ (best for comic readers)",
                        variable=self.format, value="cbz").pack(side="left")
        ttk.Radiobutton(fmt_frame, text="PDF",
                        variable=self.format, value="pdf").pack(side="left", padx=12)
        ttk.Radiobutton(fmt_frame, text="Both",
                        variable=self.format, value="both").pack(side="left")
        row += 1

        # --- Action buttons --------------------------------------------------
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky="w", **pad)
        self.convert_btn = ttk.Button(btn_frame, text="Convert",
                                      command=self._start)
        self.convert_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btn_frame, text="Cancel",
                                     command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        row += 1

        # --- Progress + log --------------------------------------------------
        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.grid(row=row, column=0, columnspan=3, sticky="ew", padx=10)
        row += 1

        self.log = scrolledtext.ScrolledText(main, height=16, wrap="word",
                                             state="disabled")
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew",
                      padx=10, pady=(6, 4))
        main.rowconfigure(row, weight=1)
        row += 1

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(main, textvariable=self.status, relief="sunken",
                  anchor="w").grid(row=row, column=0, columnspan=3,
                                   sticky="ew", padx=10, pady=(0, 4))

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._check_environment()
        self.root.after(100, self._drain_log)

    # -- helpers -------------------------------------------------------------
    def _check_environment(self):
        """Warn up front about the two things that stop conversion cold."""
        problems = []
        if self.converter_python is None:
            problems.append(
                "Could not find 32-bit Python 3.10. Install it (see the README) "
                "and launch this program with it.")
        if find_dll_dir() is None:
            problems.append(
                "The reader DLLs were not found. Put BondiReader.DJVU.dll, "
                "msvcr71.dll and msvcp71.dll in the 'dlls' folder "
                "(see dlls\\PUT_YOUR_DLLS_HERE.txt).")
        if not os.path.exists(ENGINE):
            problems.append(f"playboy_convert.py was not found next to this program.")

        if problems:
            self._log("Setup needs attention before you can convert:\n")
            for p in problems:
                self._log(f"  - {p}\n")
            self.status.set("Setup incomplete - see the messages above.")
            self.convert_btn.config(state="disabled")
        else:
            self._log("Ready. Choose what to convert and press Convert.\n")

    def _clear_path(self):
        self.path_var.set("")

    def _browse_source(self):
        if self.mode.get() == "folder":
            path = filedialog.askdirectory(title="Choose the folder of .djvu issues")
        else:
            path = filedialog.askopenfilename(
                title="Choose a .djvu issue",
                filetypes=[("DJVU files", "*.djvu"), ("All files", "*.*")])
        if path:
            self.path_var.set(os.path.normpath(path))

    def _browse_output(self):
        path = filedialog.askdirectory(title="Choose where to save converted files")
        if path:
            self.output_var.set(os.path.normpath(path))

    def _log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    # -- run/cancel ----------------------------------------------------------
    def _start(self):
        source = self.path_var.get().strip().strip('"')
        output = self.output_var.get().strip().strip('"')

        if not source:
            messagebox.showwarning("Nothing selected",
                                   "Choose a folder or a .djvu file to convert.")
            return
        if self.mode.get() == "folder" and not os.path.isdir(source):
            messagebox.showerror("Not a folder",
                                 "The source you chose is not a folder.")
            return
        if self.mode.get() == "file" and not (
                os.path.isfile(source) and source.lower().endswith(".djvu")):
            messagebox.showerror("Not a .djvu file",
                                 "The source you chose is not a .djvu file.")
            return
        if not output:
            messagebox.showwarning("No destination",
                                   "Choose a folder to save the converted files.")
            return

        cmd = [
            self.converter_python, ENGINE, source,
            "--format", self.format.get(),
            "--output_dir", output,
        ]

        self.convert_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress.start(12)
        self.status.set("Converting... this can take several minutes per issue.")
        self._log("\n" + "=" * 60 + "\nStarting conversion...\n" + "=" * 60 + "\n")

        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _run(self, cmd):
        # Unbuffered so per-page progress from the engine (and its per-file
        # child processes) appears live instead of in one lump at the end.
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=SCRIPT_DIR, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, creationflags=creationflags,
            )
        except Exception as e:
            self.log_queue.put(("line", f"[ERROR] Could not start converter: {e}\n"))
            self.log_queue.put(("done", 1))
            return

        for line in self.proc.stdout:
            self.log_queue.put(("line", line))
        self.proc.stdout.close()
        code = self.proc.wait()
        self.log_queue.put(("done", code))

    def _cancel(self):
        if self.proc and self.proc.poll() is None:
            self.status.set("Cancelling...")
            # The engine may have spawned per-file child processes; kill the
            # whole tree so nothing is left running.
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                try:
                    self.proc.terminate()
                except Exception:
                    pass

    def _drain_log(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "line":
                    self._log(payload)
                elif kind == "done":
                    self._finish(payload)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def _finish(self, code):
        self.proc = None
        self.progress.stop()
        self.convert_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        if code == 0:
            self.status.set("Done. Your files are in the 'Save to' folder.")
            self._log("\nConversion finished successfully.\n")
        else:
            self.status.set(f"Finished with problems (exit code {code}). "
                            "See the log above.")
            self._log(f"\nConversion ended with exit code {code}. "
                      "Some or all files may not have been created.\n")

    def _on_close(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno(
                    "Conversion running",
                    "A conversion is still running. Stop it and quit?"):
                return
            self._cancel()
        self.root.destroy()


def main():
    root = tk.Tk()
    ConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
