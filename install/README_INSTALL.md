# Install notes

Audion Doc to PDF is a Windows portable GUI/CLI tool.

## Runtime dependencies

The portable runtime should include:

- `pypdf`
- `nicegui`
- `pyyaml`
- `rich`
- `pywebview`
- `setuptools`
- `wheel`

Conversion of Office documents is delegated to `system_core\office_export.ps1` and requires locally installed Microsoft Office desktop applications.

## Project folders

Run this after unpacking or after cleanup:

```bat
install\init_folders.cmd
```

It creates `input`, `output`, `logs`, `report`, `release`, `runtime`, `wheelhouse`, and the install/license support folders.

## GUI

Start the GUI with:

```bat
launcher_gui.cmd
```

The GUI starts `system_core\ui_nicegui\window.py`, which launches the NiceGUI server and opens a pywebview desktop window.

## Reproducible payloads

Python runtime, wheelhouse, portable PowerShell and FZF are reproducible tool payloads. Install/update scripts may resolve latest upstream artifacts and cleanly replace only their owned targets: `runtime\`, `wheelhouse\`, `system_core\powershell\`, and `system_core\fzf.exe`.

---

## Current Builder Order And Dependency Hygiene

`builder_main.cmd` uses fixed numeric entries. Keep the bootstrap order stable: `[01] PYTHON ENV CMD`, `[02] PYTHON ENV PS`, `[03] FZF`, `[04] POWERSHELL`, then project-specific payload installers and one-time maintenance/diagnostic actions below.

Current builder install/maintenance map:

```text
[01] PYTHON ENV CMD
[02] PYTHON ENV PS
[03] FZF
[04] POWERSHELL
[09] PORTABLE OFFLINE
[70] CLEAN INSTALL CACHE
[71] VERIFY / DOCTOR
[72] CMD ENCODING CHECK
[77] MAKE RELEASE ARCHIVE
[90] PROJECT LAUNCHER
[95] OPEN install
[96] OPEN runtime
[97] OPEN wheelhouse
[98] OPEN licenses
[99] OPEN release
[00] EXIT
```

Project-specific payload entries before diagnostics:

No project-specific external payload installer before diagnostics.

Dependency hygiene rules:

- Python Embedded tracks the latest `3.12.x`; do not pin a concrete patch version in docs or scripts.
- Use the active embedded Python `_pth` file for path edits; do not hard-code a concrete filename.
- Bootstrap installs must include `setuptools`, `wheel`, and `packaging` before building or installing project wheels.
- `runtime\`, `wheelhouse\`, `system_core\powershell\`, `system_core\fzf.exe`, browser payloads, and external tool folders are reproducible payloads. Install/update scripts may cleanly replace only their owned targets.
- GPL or unknown-license external tools are explicit install/update payloads. Prefer GUI install buttons where the project exposes them, or fixed builder entries otherwise; do not silently bundle them as default source contents.
- `install\Clean-Install-Cache.cmd` / `.ps1` is the general install-cache cleanup. It removes transient `install\download\` artifacts (preserving `.gitkeep`, `get-pip.py`, and `7z*-extra.7z`), exact installer staging dirs `system_core\_pwsh_tmp` / `system_core\_fzf_tmp`, and Python bytecode caches outside runtime, wheelhouse, and user-data zones.
- `cleanup_project.cmd` is a separate source/release cleanup tool. It can remove runtime payloads and user-output zones after explicit confirmation; do not describe it as the general install-cache cleaner and do not wire it into install flow.


