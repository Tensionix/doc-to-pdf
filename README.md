# Audion Doc to PDF

<!-- audion:release -->
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0b6db8?style=flat-square&logo=windows&logoColor=white)](https://audion.dev/downloads/doc-to-pdf) [![Release](https://img.shields.io/github/v/release/Tensionix/doc-to-pdf?style=flat-square&label=release&color=e08a63)](https://github.com/Tensionix/doc-to-pdf/releases/latest) [![Downloads](https://img.shields.io/github/downloads/Tensionix/doc-to-pdf/total?style=flat-square&label=downloads&color=5fd08a)](https://github.com/Tensionix/doc-to-pdf/releases) [![License](https://img.shields.io/github/license/Tensionix/doc-to-pdf?style=flat-square&color=5fd08a&logo=apache&logoColor=white&cacheSeconds=3600)](https://github.com/Tensionix/doc-to-pdf/blob/main/LICENSE)

**Version 1.6.1** · 2026-08-25 · 182.1 MB

- [Direct download](https://audion.dev/get/doc-to-pdf/1.6.1/Audion_Doc_to_PDF_v1.6.1_Full.zip) — unmetered, no rate limits
- [Project page](https://audion.dev/downloads/doc-to-pdf) — every version and how to install

<img src="docs/screenshot.png" alt="The program window" width="560">

`SHA-256: 79187aa82ff17320b8817a7d28e04afbc62ecdbb4e516a01698a0f9393e3bf4f`

---

An **Audion** tool, published by [Tensionix](https://github.com/Tensionix).
<!-- /audion:release -->

Portable Windows tool for batch conversion of Word, Excel, and PowerPoint documents through native Microsoft Office export, plus common processing of ready PDFs.

## Features

- recursive folder conversion with mirrored output structure;
- direct conversion of one Office file;
- `16:9` or A-series post-crop for presentation exports;
- presentation content scaling;
- PDF splitting, aspect/margin cropping, numbering, and content scaling;
- metadata under `report\latest\metadata` and run archives;
- shared Source/Target routes across GUI and CLI.

- Word: `.doc`, `.docx`, `.docm`, `.rtf`, `.txt`, `.odt`
- Excel: `.xls`, `.xlsx`, `.xlsm`, `.xlsb`, `.csv`, `.ods`
- PowerPoint: `.ppt`, `.pptx`, `.pptm`, `.odp`

## GUI

Run `launcher_gui.cmd`. The canonical Workbench I/O at the upper left defines direct routes:

- `Source` is a folder or one Office/PDF file;
- `Target` is the result folder;
- source data is not copied into staging or a cache;
- `input` and `output` remain safe initial values and CLI defaults.

Path history is local and excluded from Git. Pinning, locking, file/folder selection, list view, reset, and guarded deletion match the other Audion Workbench projects.

See `docs\GUI.md` for the full GUI guide.

## CLI

Convert default `input` to `output`:

```bat
python system_core\main.py batch --recursive --extensions docx,pptx,xlsx
```

Convert custom folders:

```bat
python system_core\main.py batch --recursive --input-dir "D:\DOCS" --output-dir "E:\PDF" --extensions docx,pptx,xlsx
```

Convert one file:

```bat
python system_core\main.py file --input "D:\DOCS\report.docx" --output-dir "E:\PDF"
```

Process one PDF or a folder of PDFs through explicit routes:

```bat
python system_core\main.py pdf-crop-aspect --mode "16:9" --input-dir "D:\PDF\source.pdf" --output-dir "E:\PDF"
python system_core\main.py pdf-scale-content --percent 98 --input-dir "D:\PDF" --output-dir "E:\PDF"
```

Omitting `--input-dir/--output-dir` preserves the legacy `input -> output` behavior.

## Working data

- `input`, `output`: default routes;
- `report`: metadata and run archives;
- `logs`: CLI and GUI logs;
- `config`: manifest, themes, and settings.

`cleanup_project.cmd` removes only the generated/runtime content declared by that script. Distribution checks include `install\Check-CmdEncoding.cmd` and smoke/doctor commands.

## Requirements

- Windows;
- installed Microsoft Office desktop applications;
- the project portable runtime or compatible Python;
- `pypdf`, `nicegui`, `pyyaml`, `rich`, `pywebview`.

Primary files: `launcher_gui.cmd`, `system_core\main.py`, `system_core\office_export.ps1`, `system_core\ui_nicegui\app.py`, `system_core\ui_nicegui\workbench.py`, `config\tool_manifest.yaml`.
