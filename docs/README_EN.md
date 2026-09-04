# Audion Doc to PDF

[Русский](README_RU.md) · [User Guide](USER_GUIDE_EN.md)

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

* [User Guide](USER_GUIDE_EN.md) — step by step.

---

## Technical Reference

### Requirement

An installed Microsoft Office: it performs the export, the program only drives the
process.

### Workbench Naming

One shared vocabulary across all Audion projects: **Source**, **Add file…**,
**Target**, **Reset**, **Delete**, **List**.
