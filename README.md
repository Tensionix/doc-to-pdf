# Audion Doc to PDF

<!-- audion:release -->
<p align="center">
  <a href="https://audion.dev/downloads/doc-to-pdf"><img alt="Windows" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0b6db8?style=flat-square&logo=windows&logoColor=white"></a>
  <a href="https://github.com/Tensionix/doc-to-pdf/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/Tensionix/doc-to-pdf?style=flat-square&label=release&color=e08a63"></a>
  <a href="https://github.com/Tensionix/doc-to-pdf/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/Tensionix/doc-to-pdf/total?style=flat-square&label=downloads&color=5fd08a"></a>
  <a href="https://github.com/Tensionix/doc-to-pdf/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/Tensionix/doc-to-pdf?style=flat-square&color=5fd08a&logo=apache&logoColor=white&cacheSeconds=3600"></a>
</p>

**Version 1.6.2** · 2026-09-04 · 181.9 MB

- [Direct download](https://audion.dev/get/doc-to-pdf/1.6.2/Audion_Doc_to_PDF_v1.6.2_Full.zip) — unmetered, no rate limits
- [Project page](https://audion.dev/downloads/doc-to-pdf) — every version and how to install

<p align="center"><img src="docs/screenshot.png" alt="The program window" width="560"></p>

`SHA-256: 7f4d2fe6b660caa8e67d624818c9bc56ad1948cdf1d2967c8a4d331d90064220`

---

An **Audion** tool, published by [Tensionix](https://github.com/Tensionix).
<!-- /audion:release -->


[Русский](docs/README_RU.md) · [User Guide](docs/USER_GUIDE_EN.md)

**Contents**

- [Why It Exists](#why-it-exists)
- [Principles](#principles)
- [What It Can Do](#what-it-can-do)
- [Next](#next)
- [Technical Reference](#technical-reference)
  - [Requirement](#requirement)
  - [Workbench Naming](#workbench-naming)

Batch conversion of Word, Excel, and PowerPoint into PDF — through the native
export of Office itself. Plus routine processing of existing PDFs.

## Why It Exists

There are a dozen ways to get a PDF out of an Office document, and almost all of
them spoil the result: third-party engines lose fonts, break numbering, move
tables elsewhere. The only one that reliably produces what you see on screen is
Office itself.

But Office cannot do it in bulk. Opening two hundred files and pressing "Save as
PDF" two hundred times is not work for a human.

The program takes that over: **the export stays native**, and the batching is
added around it.

## Principles

**The folder structure is preserved.** The walk is recursive and the output
mirrors the source tree. Two hundred files from twenty folders do not collapse
into one.

**Existing PDFs are processed too.** Not everything comes from Office: some
material is already PDF and needs the same treatment — cropping to format,
assembly, splitting.

**Presentations are cropped afterwards.** The export produces the page as it is,
and fitting to `16:9` or an A-series size is a separate step — so the original
export stays unspoilt.

## What It Can Do

Recursive folder conversion preserving structure, single-file conversion,
cropping presentations to `16:9` or A-series, routine processing of existing PDFs.

## Next

* [User Guide](docs/USER_GUIDE_EN.md) — step by step.

---

## Technical Reference

### Requirement

An installed Microsoft Office: it performs the export, the program only drives the
process.

### Workbench Naming

One shared vocabulary across all Audion projects: **Source**, **Add file…**,
**Target**, **Reset**, **Delete**, **List**.
