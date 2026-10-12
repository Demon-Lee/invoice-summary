import argparse
import ctypes
import json
import sys
import tempfile
import traceback
from pathlib import Path

# Static imports ensure these engine dependencies are included in the offline build.
import pdfplumber
import openpyxl
from invoice_desktop import __version__
from invoice_desktop.controller import resource_root
from invoice_desktop.updates import read_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", metavar="OUTPUT_JSON")
    parser.add_argument("--smoke-gui", metavar="OUTPUT_JSON")
    parser.add_argument("--pipeline-smoke", metavar="PDF")
    parser.add_argument("--output", metavar="OUTPUT_JSON")
    args = parser.parse_args()
    output = args.diagnose or args.smoke_gui or args.output
    if output and Path(output).suffix.lower() != ".json":
        raise ValueError("诊断输出仅支持独立的 .json 文件")
    if args.pipeline_smoke:
        if not args.output or Path(args.output).resolve() == Path(args.pipeline_smoke).resolve():
            raise ValueError("流程诊断需要独立的 --output JSON 路径")
        from invoice_desktop.diagnostics import pipeline_smoke
        data = pipeline_smoke(args.pipeline_smoke, resource_root() / "engine")
    elif args.diagnose:
        import tkinter
        from invoice_desktop.diagnostics import update_smoke
        data = {"software_version": __version__, "engine_version": read_manifest(resource_root() / "engine")["version"],
                "pdfplumber": pdfplumber.__version__, "openpyxl": openpyxl.__version__, "tkinter": tkinter.TkVersion,
                "resources": all((resource_root() / "resources" / name).exists() for name in ("check_excel.ps1", "run_excel.ps1")),
                "offline_update": update_smoke(resource_root() / "engine")}
    else:
        import tkinter as tk
        from invoice_desktop.app import App
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        root = tk.Tk()
        if args.smoke_gui:
            root.withdraw()
            with tempfile.TemporaryDirectory(prefix="invoice-ui-check-") as tmp:
                application = App(root, tmp)
                root.update_idletasks()
                data = {"status": "started", "title": root.title(), "engine_version": application.store.version(), "execute_disabled": str(application.execute.cget("state")) == "disabled"}
                root.destroy()
        else:
            App(root)
            root.mainloop()
            return 0
    Path(output).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        if any(flag in sys.argv for flag in ("--diagnose", "--smoke-gui", "--pipeline-smoke")):
            if sys.stderr:
                traceback.print_exc()
            raise SystemExit(1)
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("发票汇总助手未能启动", str(exc))
            root.destroy()
        finally:
            if sys.stderr:
                traceback.print_exc()
        raise SystemExit(1)

