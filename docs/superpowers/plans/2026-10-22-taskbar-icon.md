# DPI-aware taskbar icon repair

> Execute inline in the existing clean checkout. This is a repair of the existing icon's display; retain its drawing, colors and application workflows.

**Goal:** Load a suitably sized Windows taskbar icon at the display scale used by the application.

**Evidence:** `App._build` uses Tk 8.6 `iconbitmap`. Tk's Windows `GetIcon` selects fixed 16/32 pixel images. The existing ICO has 16/32/48/64/128/256 images; 125% and 175% dimensions are missing. Application startup already requests system DPI awareness; retain that setting.

**Constraints:** Windows 10/11, existing Pillow and ctypes only. No new dependencies, tests, GUI launches, Excel operations or invoice processing. Leave skill, recognition snapshots, workbook handling and PDF export unchanged. Do not upload this update unless requested.

## Steps

- [ ] Add `invoice_desktop/window_icon.py`: retain Tk's default ICO for child dialogs and fallback; after the root frame exists, load independent big/small icon handles from that ICO using the system metrics for the window DPI, and send `WM_SETICON` to the decorative frame. Own only handles loaded here, release them after replacement/destruction, cancel pending callbacks on root destruction, and keep fallback icons on an optional native failure.
- [ ] Call the helper from `App._build`. Reapply after a root Map event if the frame or requested sizes change. Avoid window-procedure hooks and changes to process DPI awareness.
- [ ] Update `tools/release_assets.py` to render each 16/20/24/28/32/36/40/48/56/64/72/80/96/112/128/144/160/192/224/256 pixel image directly from the existing high-resolution drawing. Preserve the design and embed all images in the ICO used by the executable and runtime.
- [ ] Bump the version and external guide to 1.1.19. Review diff, compile source without executing application code, and inspect ICO image sizes and embedded executable resources.
- [ ] Build with the existing portable build script and preserve the current recognition directory. Stage and hash-check all output files; before replacing `release/InvoiceSummary`, verify its absolute path is within `release`, has no reparse points, and its executable is not running. Archive the previous directory rather than deleting it.
- [ ] Package original release/source snapshots, verify ZIP members against files and tracked source, and record scope and limitations in `docs/release-checks.md`. Actual taskbar rendering at different display scales remains for user confirmation; static checks are not a GUI run.

## Source references

- Tk 8.6 Windows window manager: https://github.com/tcltk/tk/blob/core-8-6-branch/win/tkWinWm.c (`GetIcon` and `WinSetIcon`).
- Windows icon metrics and ownership: https://learn.microsoft.com/en-us/windows/win32/menurc/about-icons

