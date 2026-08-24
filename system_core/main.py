from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

SYSTEM_CORE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SYSTEM_CORE_DIR.parent
for import_path in (SYSTEM_CORE_DIR, PROJECT_ROOT):
    import_path_text = str(import_path)
    if import_path_text not in sys.path:
        sys.path.insert(0, import_path_text)

from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from pypdf.annotations import FreeText
from pypdf.generic import RectangleObject

try:
    from ansi_terminal import strip_ansi
except ImportError:
    from system_core.ansi_terminal import strip_ansi


WORD_EXTS = {".doc", ".docx", ".docm", ".rtf", ".txt", ".odt"}
EXCEL_EXTS = {".xls", ".xlsx", ".xlsm", ".xlsb", ".csv", ".ods"}
POWERPOINT_EXTS = {".ppt", ".pptx", ".pptm", ".odp"}
OFFICE_EXTS = WORD_EXTS | EXCEL_EXTS | POWERPOINT_EXTS

DEFAULT_SETTINGS = {
    "skip_already_cropped_pptx_pdfs": True,
}

REPORT_RUN_STAMP = time.strftime("%Y-%m-%d_%H-%M-%S")


@dataclass
class Settings:
    skip_already_cropped_pptx_pdfs: bool


class ConversionError(RuntimeError):
    pass


def configure_stdio() -> None:
    for stream in [sys.stdout, sys.stderr]:
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def load_settings(root: Path) -> Settings:
    payload = dict(DEFAULT_SETTINGS)
    cfg_path = root / "config" / "settings.json"
    if cfg_path.exists():
        user_data = json.loads(cfg_path.read_text(encoding="utf-8"))
        payload.update(user_data)

    return Settings(
        skip_already_cropped_pptx_pdfs=bool(payload["skip_already_cropped_pptx_pdfs"]),
    )


def ensure_dirs(root: Path) -> dict[str, Path]:
    mapping = {
        "input": root / "input",
        "output": root / "output",
        "logs": root / "logs",
        "report": root / "report",
        "config": root / "config",
    }
    for path in mapping.values():
        path.mkdir(parents=True, exist_ok=True)
    return mapping


def log_message(log_file: Path, message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_file.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {strip_ansi(message)}\n")


def format_duration(seconds: float) -> str:
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def resolve_powershell(root: Path) -> list[str]:
    candidates = [
        root / "system_core" / "powershell" / "pwsh.exe",
        Path(shutil.which("pwsh") or ""),
        Path(shutil.which("powershell") or ""),
        Path(shutil.which("powershell.exe") or ""),
    ]
    for candidate in candidates:
        if candidate and str(candidate) and candidate.exists():
            if candidate.name.lower().startswith("pwsh"):
                return [str(candidate), "-NoProfile", "-WindowStyle", "Hidden"]
            return [str(candidate), "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass"]
    raise ConversionError("PowerShell was not found.")


def hidden_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def hidden_creationflags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def run_subprocess(
    cmd: list[str],
    log_file: Path,
    timeout: int | None = None,
    progress_hook: Callable[[float], None] | None = None,
    progress_interval: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    rendered = " ".join(f'"{part}"' if " " in part else part for part in cmd)
    log_message(log_file, "RUN: " + rendered)
    started = time.perf_counter()
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        startupinfo=hidden_startupinfo(),
        creationflags=hidden_creationflags(),
    )

    while True:
        elapsed = time.perf_counter() - started
        remaining = None if timeout is None else max(0.1, timeout - elapsed)
        wait_timeout = progress_interval if remaining is None else min(progress_interval, remaining)
        try:
            stdout, stderr = process.communicate(timeout=wait_timeout)
            completed = subprocess.CompletedProcess(
                cmd,
                process.returncode,
                stdout,
                stderr,
            )
            break
        except subprocess.TimeoutExpired:
            if timeout is not None and elapsed >= timeout:
                process.kill()
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)
            if progress_hook is not None:
                progress_hook(elapsed)

    if completed.stdout:
        log_message(log_file, completed.stdout.strip())
    if completed.stderr:
        log_message(log_file, completed.stderr.strip())
    return completed


def is_benign_office_disconnect(stderr: str, out_pdf: Path) -> bool:
    if not out_pdf.exists() or out_pdf.stat().st_size <= 0:
        return False

    lowered = stderr.lower()
    patterns = [
        "rpc_e_disconnected",
        "0x80010108",
        "отключен от клиентов",
        "disconnected from its clients",
    ]
    return any(pattern in lowered for pattern in patterns)


def export_office_document_to_pdf(root: Path, input_path: Path, out_pdf: Path, log_file: Path) -> None:
    powershell = resolve_powershell(root)
    script_path = root / "system_core" / "office_export.ps1"
    if not script_path.exists():
        raise ConversionError("office_export.ps1 was not found.")

    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    cmd = powershell + [
        "-File",
        str(script_path),
        "-InputPath",
        str(input_path),
        "-OutputPath",
        str(out_pdf),
    ]

    completed = run_subprocess(
        cmd,
        log_file,
        timeout=600,
    )
    if completed.returncode != 0:
        stderr = completed.stderr or ""
        if is_benign_office_disconnect(stderr, out_pdf):
            log_message(
                log_file,
                f"WARN: Office COM disconnected after export, accepting existing PDF: {out_pdf}",
            )
            return
        raise ConversionError(f"Subprocess failed with exit code {completed.returncode}.")


def family_for_extension(ext: str) -> str:
    ext = ext.lower()
    if ext in WORD_EXTS:
        return "word"
    if ext in EXCEL_EXTS:
        return "excel"
    if ext in POWERPOINT_EXTS:
        return "powerpoint"
    return "unknown"


def output_relative_pdf(root: Path, pdf_path: Path, output_root: Path | None = None) -> Path:
    output_root = (output_root or root / "output").resolve()
    try:
        return pdf_path.resolve().relative_to(output_root)
    except Exception:
        return Path(pdf_path.name)


def metadata_path_for_pdf(root: Path, pdf_path: Path, output_root: Path | None = None) -> Path:
    relative_pdf = output_relative_pdf(root, pdf_path, output_root)
    return root / "report" / "latest" / "metadata" / relative_pdf.parent / f"{relative_pdf.name}.audion.json"


def run_metadata_path_for_pdf(root: Path, pdf_path: Path, output_root: Path | None = None) -> Path:
    relative_pdf = output_relative_pdf(root, pdf_path, output_root)
    return root / "report" / f"run_{REPORT_RUN_STAMP}" / "metadata" / relative_pdf.parent / f"{relative_pdf.name}.audion.json"


def run_metadata_candidates_for_pdf(
    root: Path,
    pdf_path: Path,
    output_root: Path | None = None,
) -> list[Path]:
    relative_pdf = output_relative_pdf(root, pdf_path, output_root)
    report_root = root / "report"
    if not report_root.exists():
        return []
    metadata_rel = relative_pdf.parent / f"{relative_pdf.name}.audion.json"
    pattern = (Path("run_*") / "metadata" / metadata_rel).as_posix()
    return sorted(report_root.glob(pattern), reverse=True)


def old_sidecar_metadata_path_for_pdf(root: Path, pdf_path: Path) -> Path:
    del root
    return pdf_path.with_name(pdf_path.name + ".audion.json")


def legacy_metadata_path_for_pdf(root: Path, pdf_path: Path, output_root: Path | None = None) -> Path:
    json_root = (root / "json").resolve()
    relative_pdf = output_relative_pdf(root, pdf_path, output_root)

    return json_root / relative_pdf.parent / f"{relative_pdf.name}.audion.json"


def write_metadata_payload(root: Path, pdf_path: Path, payload: dict, output_root: Path | None = None) -> None:
    for meta_path in [
        metadata_path_for_pdf(root, pdf_path, output_root),
        run_metadata_path_for_pdf(root, pdf_path, output_root),
    ]:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def write_pdf_metadata(
    root: Path,
    pdf_path: Path,
    source_path: Path,
    relative_source: str,
    family: str,
    output_root: Path | None = None,
    cropped_exact_16_9: bool = False,
) -> None:
    payload = {
        "source_path": str(source_path),
        "source_relative": relative_source.replace("/", "\\"),
        "source_extension": source_path.suffix.lower(),
        "source_family": family,
        "exported_pdf": str(pdf_path),
        "output_root": str((output_root or root / "output").resolve()),
        "cropped_exact_16_9": bool(cropped_exact_16_9),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_metadata_payload(root, pdf_path, payload, output_root)


def read_pdf_metadata(root: Path, pdf_path: Path, output_root: Path | None = None) -> dict | None:
    for meta_path in [
        metadata_path_for_pdf(root, pdf_path, output_root),
        old_sidecar_metadata_path_for_pdf(root, pdf_path),
        legacy_metadata_path_for_pdf(root, pdf_path, output_root),
        *run_metadata_candidates_for_pdf(root, pdf_path, output_root),
    ]:
        if not meta_path.exists():
            continue
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return None


def plan_output_path(
    source: Path,
    input_root: Path,
    output_root: Path,
    used_targets: dict[str, Path],
) -> tuple[Path, str]:
    relative = source.relative_to(input_root)
    out_dir = output_root / relative.parent
    base_name = source.stem
    target = out_dir / f"{base_name}.pdf"
    key = str(target).lower()

    if key not in used_targets:
        used_targets[key] = source
        return target, relative.as_posix()

    existing_source = used_targets[key]
    if existing_source.resolve() == source.resolve():
        return target, relative.as_posix()

    ext_tag = source.suffix.lower().lstrip(".") or "file"
    candidate = out_dir / f"{base_name}__{ext_tag}.pdf"
    index = 2
    while str(candidate).lower() in used_targets:
        candidate = out_dir / f"{base_name}__{ext_tag}_{index}.pdf"
        index += 1

    used_targets[str(candidate).lower()] = source
    return candidate, relative.as_posix()


def parse_extension_filter(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    extensions: set[str] = set()
    for chunk in raw.split(","):
        item = chunk.strip().lower()
        if not item:
            continue
        if not item.startswith("."):
            item = f".{item}"
        if item not in OFFICE_EXTS:
            raise ConversionError(f"Unsupported Office extension filter: {item}")
        extensions.add(item)
    return extensions or None


def iter_supported_files(input_dir: Path, recursive: bool, extension_filter: set[str] | None = None) -> Iterable[Path]:
    iterator = input_dir.rglob("*") if recursive else input_dir.glob("*")
    allowed_extensions = extension_filter or OFFICE_EXTS
    for path in iterator:
        if path.is_file() and path.suffix.lower() in allowed_extensions:
            yield path


def convert_one_source(
    root: Path,
    source: Path,
    input_root: Path,
    output_root: Path,
    used_targets: dict[str, Path],
    log_file: Path,
    post_crop: str = "none",
    post_scale_percent: float = 100.0,
) -> Path:
    if not source.exists():
        raise ConversionError(f"Input file does not exist: {source}")

    target, relative_source = plan_output_path(source, input_root, output_root, used_targets)
    export_office_document_to_pdf(root, source, target, log_file)
    cropped = False
    source_family = family_for_extension(source.suffix)
    if post_crop != "none" and source_family == "powerpoint":
        crop_pdf_to_aspect_inplace(target, post_crop)
        cropped = True
    if post_scale_percent < 100.0 and source_family == "powerpoint":
        scale_pdf_content_inplace(target, post_scale_percent)

    write_pdf_metadata(
        root=root,
        pdf_path=target,
        source_path=source,
        relative_source=relative_source,
        family=family_for_extension(source.suffix),
        output_root=output_root,
        cropped_exact_16_9=(post_crop == "16:9" and cropped),
    )
    log_message(log_file, f"OK -> {target}")
    return target


def crop_pdf_to_aspect_inplace(pdf_path: Path, mode: str) -> None:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()

    for page in reader.pages:
        left = float(page.mediabox.left)
        bottom = float(page.mediabox.bottom)
        right = float(page.mediabox.right)
        top = float(page.mediabox.top)

        width = right - left
        height = top - bottom
        if width <= 0 or height <= 0:
            raise ConversionError(f"Invalid page size: {pdf_path}")

        if mode == "16:9":
            target_ratio = 16.0 / 9.0
        elif mode == "a-series":
            target_ratio = math.sqrt(2.0) if width >= height else 1.0 / math.sqrt(2.0)
        else:
            raise ConversionError(f"Unsupported crop aspect mode: {mode}")

        current_ratio = width / height
        if abs(current_ratio - target_ratio) < 0.0001:
            new_box = RectangleObject((left, bottom, right, top))
        elif current_ratio > target_ratio:
            target_width = height * target_ratio
            trim_each_side = (width - target_width) / 2.0
            new_box = RectangleObject((left + trim_each_side, bottom, right - trim_each_side, top))
        else:
            target_height = width / target_ratio
            trim_each_side = (height - target_height) / 2.0
            new_box = RectangleObject((left, bottom + trim_each_side, right, top - trim_each_side))
        page.mediabox = new_box
        page.cropbox = new_box
        page.trimbox = new_box
        page.bleedbox = new_box
        page.artbox = new_box
        writer.add_page(page)

    tmp_path = pdf_path.with_name(pdf_path.name + ".tmp")
    with tmp_path.open("wb") as fh:
        writer.write(fh)
    tmp_path.replace(pdf_path)


def crop_pdf_to_exact_16_9_inplace(pdf_path: Path) -> None:
    crop_pdf_to_aspect_inplace(pdf_path, "16:9")


def mm_to_points(value: float) -> float:
    return value * 72.0 / 25.4


def validate_scale_percent(percent: float) -> float:
    if percent <= 0 or percent > 100:
        raise ConversionError("Scale percent must be greater than 0 and no more than 100.")
    return percent


def scale_pdf_content_inplace(pdf_path: Path, percent: float) -> None:
    percent = validate_scale_percent(percent)
    scale = percent / 100.0
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for page in reader.pages:
        new_page = copy.deepcopy(page)
        left = float(new_page.mediabox.left)
        bottom = float(new_page.mediabox.bottom)
        right = float(new_page.mediabox.right)
        top = float(new_page.mediabox.top)
        center_x = left + (right - left) / 2.0
        center_y = bottom + (top - bottom) / 2.0
        transform = Transformation().scale(scale).translate(
            tx=(1.0 - scale) * center_x,
            ty=(1.0 - scale) * center_y,
        )
        new_page.add_transformation(transform)
        writer.add_page(new_page)
    write_pdf(writer, pdf_path)


def scale_pdf_content_copy(source: Path, target: Path, percent: float) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    scale_pdf_content_inplace(target, percent)


def iter_input_pdfs(input_root: Path) -> list[Path]:
    if not input_root.exists():
        raise ConversionError(f"Input path does not exist: {input_root}")
    if input_root.is_file():
        files = [input_root] if input_root.suffix.lower() == ".pdf" else []
    elif input_root.is_dir():
        files = sorted(path for path in input_root.rglob("*.pdf") if path.is_file())
    else:
        files = []
    if not files:
        raise ConversionError(f"No PDF files were found in: {input_root}")
    return files


def pdf_output_path(source: Path, input_root: Path, output_root: Path, suffix: str) -> Path:
    base_root = input_root.parent if input_root.is_file() else input_root
    relative = source.relative_to(base_root)
    return output_root / relative.parent / f"{source.stem}{suffix}.pdf"


def resolve_pdf_io(root: Path, input_dir: str | None = None, output_dir: str | None = None) -> tuple[Path, Path]:
    dirs = ensure_dirs(root)
    input_root = Path(input_dir).expanduser().resolve() if input_dir else dirs["input"].resolve()
    output_root = Path(output_dir).expanduser().resolve() if output_dir else dirs["output"].resolve()
    if not input_root.exists():
        raise ConversionError(f"Input path does not exist: {input_root}")
    if output_root.exists() and not output_root.is_dir():
        raise ConversionError(f"Output path is not a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    return input_root, output_root


def set_all_page_boxes(page: PageObject, rect: RectangleObject) -> None:
    page.mediabox = rect
    page.cropbox = rect
    page.trimbox = rect
    page.bleedbox = rect
    page.artbox = rect


def write_pdf(writer: PdfWriter, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(target.name + ".tmp")
    with tmp_path.open("wb") as fh:
        writer.write(fh)
    tmp_path.replace(target)


def split_pdf_50_50(source: Path, target: Path, orientation: str, skip_cover: bool = False) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    pages = list(reader.pages)
    last_page_index = len(pages) - 1
    for page_index, page in enumerate(pages):
        if skip_cover and page_index in {0, last_page_index}:
            writer.add_page(copy.deepcopy(page))
            continue
        left = float(page.mediabox.left)
        bottom = float(page.mediabox.bottom)
        right = float(page.mediabox.right)
        top = float(page.mediabox.top)
        if orientation == "vertical":
            middle = left + (right - left) / 2.0
            boxes = [
                RectangleObject((left, bottom, middle, top)),
                RectangleObject((middle, bottom, right, top)),
            ]
        else:
            middle = bottom + (top - bottom) / 2.0
            boxes = [
                RectangleObject((left, middle, right, top)),
                RectangleObject((left, bottom, right, middle)),
            ]
        for box in boxes:
            new_page = copy.deepcopy(page)
            set_all_page_boxes(new_page, box)
            writer.add_page(new_page)
    write_pdf(writer, target)


def crop_pdf_margins(source: Path, target: Path, left_mm: float, right_mm: float, top_mm: float, bottom_mm: float) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    left_trim = mm_to_points(left_mm)
    right_trim = mm_to_points(right_mm)
    top_trim = mm_to_points(top_mm)
    bottom_trim = mm_to_points(bottom_mm)
    for page in reader.pages:
        left = float(page.mediabox.left) + left_trim
        bottom = float(page.mediabox.bottom) + bottom_trim
        right = float(page.mediabox.right) - right_trim
        top = float(page.mediabox.top) - top_trim
        if right <= left or top <= bottom:
            raise ConversionError(f"Margins are larger than a page in: {source}")
        new_page = copy.deepcopy(page)
        set_all_page_boxes(new_page, RectangleObject((left, bottom, right, top)))
        writer.add_page(new_page)
    write_pdf(writer, target)


def crop_pdf_to_aspect_copy(source: Path, target: Path, mode: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    crop_pdf_to_aspect_inplace(target, mode)


def page_number_rect(page: PageObject, text: str, position: str, offset_mm: float, font_size: int = 10) -> tuple[float, float, float, float]:
    left = float(page.mediabox.left)
    bottom = float(page.mediabox.bottom)
    right = float(page.mediabox.right)
    top = float(page.mediabox.top)
    offset = mm_to_points(offset_mm)
    text_width = max(1, len(text)) * font_size * 0.5
    horizontal = "center"
    vertical = "bottom"
    if "-" in position:
        vertical, horizontal = position.split("-", 1)
    if horizontal == "left":
        x = left + offset
    elif horizontal == "right":
        x = right - offset - text_width
    else:
        x = left + ((right - left) - text_width) / 2.0
    y = top - offset - font_size if vertical == "top" else bottom + offset
    return (x, y, x + text_width + 4, y + font_size + 4)


def add_page_numbers(source: Path, target: Path, start_page: int, start_number: int, offset_mm: float, position: str) -> None:
    reader = PdfReader(str(source))
    writer = PdfWriter()
    page_start_index = max(0, start_page - 1)
    for index, page in enumerate(reader.pages):
        new_page = copy.deepcopy(page)
        writer.add_page(new_page)
        if index >= page_start_index:
            text = str(start_number + index - page_start_index)
            writer.add_annotation(
                index,
                FreeText(
                    text=text,
                    rect=page_number_rect(new_page, text, position, offset_mm),
                    font_size="10pt",
                    font_color="000000",
                    border_color=None,
                    background_color=None,
                ),
            )
    write_pdf(writer, target)


def cmd_pdf_split(
    root: Path,
    log_file: Path,
    orientation: str,
    skip_cover: bool = False,
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> int:
    input_root, output_root = resolve_pdf_io(root, input_dir, output_dir)
    files = iter_input_pdfs(input_root)
    suffix = "_split_vertical" if orientation == "vertical" else "_split_horizontal"
    if skip_cover:
        suffix += "_except_cover"
    for index, source in enumerate(files, start=1):
        target = pdf_output_path(source, input_root, output_root, suffix)
        cover_note = " except cover" if skip_cover else ""
        print(f"[INFO] [{index}/{len(files)}] Splitting{cover_note}: {source.relative_to(input_root)}")
        split_pdf_50_50(source, target, orientation, skip_cover=skip_cover)
        print(f"[OK] [{index}/{len(files)}] {target}")
        log_message(log_file, f"SPLIT {orientation}{cover_note} -> {target}")
    return 0


def cmd_pdf_crop_margins(
    root: Path,
    log_file: Path,
    left_mm: float,
    right_mm: float,
    top_mm: float,
    bottom_mm: float,
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> int:
    input_root, output_root = resolve_pdf_io(root, input_dir, output_dir)
    files = iter_input_pdfs(input_root)
    for index, source in enumerate(files, start=1):
        target = pdf_output_path(source, input_root, output_root, "_crop_margins")
        print(f"[INFO] [{index}/{len(files)}] Cropping margins: {source.relative_to(input_root)}")
        crop_pdf_margins(source, target, left_mm, right_mm, top_mm, bottom_mm)
        print(f"[OK] [{index}/{len(files)}] {target}")
        log_message(log_file, f"CROP MARGINS -> {target}")
    return 0


def cmd_pdf_crop_aspect(
    root: Path,
    log_file: Path,
    mode: str,
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> int:
    input_root, output_root = resolve_pdf_io(root, input_dir, output_dir)
    files = iter_input_pdfs(input_root)
    suffix = "_16x9" if mode == "16:9" else "_a_series"
    for index, source in enumerate(files, start=1):
        target = pdf_output_path(source, input_root, output_root, suffix)
        print(f"[INFO] [{index}/{len(files)}] Cropping aspect: {source.relative_to(input_root)}")
        crop_pdf_to_aspect_copy(source, target, mode)
        print(f"[OK] [{index}/{len(files)}] {target}")
        log_message(log_file, f"CROP ASPECT {mode} -> {target}")
    return 0


def cmd_pdf_scale_content(
    root: Path,
    log_file: Path,
    percent: float,
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> int:
    input_root, output_root = resolve_pdf_io(root, input_dir, output_dir)
    files = iter_input_pdfs(input_root)
    suffix = f"_content_{int(percent) if float(percent).is_integer() else str(percent).replace('.', '_')}pct"
    for index, source in enumerate(files, start=1):
        target = pdf_output_path(source, input_root, output_root, suffix)
        print(f"[INFO] [{index}/{len(files)}] Scaling content: {source.relative_to(input_root)}")
        scale_pdf_content_copy(source, target, percent)
        print(f"[OK] [{index}/{len(files)}] {target}")
        log_message(log_file, f"SCALE CONTENT {percent}% -> {target}")
    return 0


def cmd_pdf_page_numbers(
    root: Path,
    log_file: Path,
    start_page: int,
    start_number: int,
    offset_mm: float,
    position: str,
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> int:
    input_root, output_root = resolve_pdf_io(root, input_dir, output_dir)
    files = iter_input_pdfs(input_root)
    for index, source in enumerate(files, start=1):
        target = pdf_output_path(source, input_root, output_root, "_page_numbers")
        print(f"[INFO] [{index}/{len(files)}] Adding page numbers: {source.relative_to(input_root)}")
        add_page_numbers(source, target, start_page, start_number, offset_mm, position)
        print(f"[OK] [{index}/{len(files)}] {target}")
        log_message(log_file, f"PAGE NUMBERS -> {target}")
    return 0


def cmd_batch(
    root: Path,
    log_file: Path,
    input_dir: str | None,
    output_dir: str | None,
    recursive: bool,
    extensions: str | None,
    post_crop: str = "none",
    post_scale_percent: float = 100.0,
) -> int:
    dirs = ensure_dirs(root)
    base_dir = Path(input_dir).expanduser().resolve() if input_dir else dirs["input"].resolve()
    output_root = Path(output_dir).expanduser().resolve() if output_dir else dirs["output"].resolve()

    if not base_dir.exists():
        raise ConversionError(f"Input directory does not exist: {base_dir}")
    if not base_dir.is_dir():
        raise ConversionError(f"Input path is not a directory: {base_dir}")
    if output_root.exists() and not output_root.is_dir():
        raise ConversionError(f"Output path is not a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    post_scale_percent = validate_scale_percent(post_scale_percent)

    extension_filter = parse_extension_filter(extensions)
    files = list(iter_supported_files(base_dir, recursive=recursive, extension_filter=extension_filter))
    if not files:
        suffix = f" for extensions: {', '.join(sorted(extension_filter))}" if extension_filter else ""
        raise ConversionError(f"No supported Office files were found in: {base_dir}{suffix}")

    batch_started = time.perf_counter()
    total_files = len(files)
    used_targets: dict[str, Path] = {}
    print(f"[INFO] Input root : {base_dir}")
    print(f"[INFO] Output root: {output_root}")
    if extension_filter:
        print(f"[INFO] Extensions : {', '.join(sorted(extension_filter))}")
    if post_crop != "none":
        print(f"[INFO] Post-crop  : {post_crop} for PowerPoint exports")
    if post_scale_percent < 100.0:
        print(f"[INFO] Post-scale : {post_scale_percent}% for PowerPoint exports")
    print(f"[INFO] Files found: {total_files}")

    failures = 0
    for index, item in enumerate(files, start=1):
        relative = item.relative_to(base_dir)
        file_started = time.perf_counter()
        print(f"[INFO] [{index}/{total_files}] Converting: {relative}")
        try:
            out_pdf = convert_one_source(
                root,
                item,
                base_dir,
                output_root,
                used_targets,
                log_file,
                post_crop=post_crop,
                post_scale_percent=post_scale_percent,
            )
            elapsed = format_duration(time.perf_counter() - file_started)
            print(f"[OK] [{index}/{total_files}] {out_pdf} ({elapsed})")
        except Exception as exc:
            failures += 1
            elapsed = format_duration(time.perf_counter() - file_started)
            print(f"[FAIL] [{index}/{total_files}] {item} :: {exc} ({elapsed})")
            log_message(log_file, f"FAIL -> {item} :: {exc} [{elapsed}]")

    batch_elapsed = format_duration(time.perf_counter() - batch_started)
    if failures:
        print(f"[RESULT] Completed with {failures} failure(s). Total time: {batch_elapsed}")
        return 2

    print(f"[RESULT] Batch completed successfully. Total time: {batch_elapsed}")
    return 0


def cmd_crop_pptx(root: Path, settings: Settings, log_file: Path, force: bool, output_dir: str | None = None) -> int:
    output_root = Path(output_dir).expanduser().resolve() if output_dir else (root / "output").resolve()
    if not output_root.exists():
        raise ConversionError(f"Output directory does not exist: {output_root}")

    pdf_files = list(output_root.rglob("*.pdf"))
    if not pdf_files:
        raise ConversionError(f"No PDFs were found in: {output_root}")

    eligible: list[Path] = []
    for pdf_path in pdf_files:
        meta = read_pdf_metadata(root, pdf_path, output_root)
        if not meta:
            continue
        if meta.get("source_family") != "powerpoint":
            continue
        if settings.skip_already_cropped_pptx_pdfs and not force and meta.get("cropped_exact_16_9"):
            continue
        eligible.append(pdf_path)

    if not eligible:
        raise ConversionError("No eligible PowerPoint-exported PDFs were found in output.")

    crop_started = time.perf_counter()
    total_files = len(eligible)
    print(f"[INFO] Eligible PowerPoint PDFs: {total_files}")
    failures = 0
    for index, pdf_path in enumerate(eligible, start=1):
        file_started = time.perf_counter()
        print(f"[INFO] [{index}/{total_files}] Cropping: {pdf_path}")
        try:
            crop_pdf_to_exact_16_9_inplace(pdf_path)
            meta = read_pdf_metadata(root, pdf_path, output_root) or {}
            meta["cropped_exact_16_9"] = True
            meta["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            write_metadata_payload(root, pdf_path, meta, output_root)
            elapsed = format_duration(time.perf_counter() - file_started)
            print(f"[OK] [{index}/{total_files}] {pdf_path} ({elapsed})")
            log_message(log_file, f"CROPPED -> {pdf_path} [{elapsed}]")
        except Exception as exc:
            failures += 1
            elapsed = format_duration(time.perf_counter() - file_started)
            print(f"[FAIL] [{index}/{total_files}] {pdf_path} :: {exc} ({elapsed})")
            log_message(log_file, f"CROP FAIL -> {pdf_path} :: {exc} [{elapsed}]")

    crop_elapsed = format_duration(time.perf_counter() - crop_started)
    if failures:
        print(f"[RESULT] Crop completed with {failures} failure(s). Total time: {crop_elapsed}")
        return 2

    print(f"[RESULT] Crop completed successfully. Total time: {crop_elapsed}")
    return 0


def cmd_file(
    root: Path,
    log_file: Path,
    input_path: str,
    input_root: str | None,
    output_dir: str | None = None,
    post_crop: str = "none",
    post_scale_percent: float = 100.0,
) -> int:
    dirs = ensure_dirs(root)
    source = Path(input_path).expanduser().resolve()
    base_dir = Path(input_root).expanduser().resolve() if input_root else source.parent
    output_root = Path(output_dir).expanduser().resolve() if output_dir else dirs["output"].resolve()

    if not source.exists():
        raise ConversionError(f"Input file does not exist: {source}")
    if not source.is_file():
        raise ConversionError(f"Input path is not a file: {source}")
    if source.suffix.lower() not in OFFICE_EXTS:
        raise ConversionError(f"Unsupported Office extension: {source.suffix.lower()}")
    if output_root.exists() and not output_root.is_dir():
        raise ConversionError(f"Output path is not a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    if base_dir not in [source.parent, *source.parents]:
        base_dir = source.parent

    if not 0 < post_scale_percent <= 100:
        raise ConversionError("Post-scale percent must be greater than 0 and at most 100.")

    started = time.perf_counter()
    out_pdf = convert_one_source(
        root,
        source,
        base_dir,
        output_root,
        {},
        log_file,
        post_crop=post_crop,
        post_scale_percent=post_scale_percent,
    )
    elapsed = format_duration(time.perf_counter() - started)
    print(f"[OK] {out_pdf} ({elapsed})")
    return 0


def cmd_info(root: Path, settings: Settings, language: str = "en") -> int:
    if language == "ru":
        print("Audion Doc to PDF")
        print(f"Корень проекта: {root}")
        print(f"Python: {sys.executable}")
        print(f"Версия Python: {sys.version.split()[0]}")
        print(f"Пропускать уже обрезанные PowerPoint PDF: {'да' if settings.skip_already_cropped_pptx_pdfs else 'нет'}")
        print("Поддерживаемые расширения Office:")
        print("  " + ", ".join(sorted(OFFICE_EXTS)))
        print("Поведение:")
        print("  - batch рекурсивно зеркалит структуру input/source в output/target")
        print("  - Word/Excel/PowerPoint экспортируются через родной Microsoft Office")
        print("  - ОБРЕЗКА PowerPoint PDF до точных 16:9 выполняется отдельной командой")
        print("  - metadata хранится в report/latest и report/run_<timestamp>/metadata")
        return 0

    payload = {
        "project_root": str(root),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "settings": {
            "skip_already_cropped_pptx_pdfs": settings.skip_already_cropped_pptx_pdfs,
        },
        "supported_office_extensions": sorted(OFFICE_EXTS),
        "behavior": {
            "batch_output_structure": "output/target mirrors input/source subfolders",
            "word_excel_powerpoint_export": "native Office ExportAsFixedFormat / Create PDF/XPS path",
            "pptx_crop_mode": "optional exact 16:9 crop for PowerPoint-exported PDFs in output",
            "metadata_sidecars": "stored under report/latest and report/run_<timestamp>/metadata, with legacy output/json fallback",
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch-convert supported Office files to PDF with preserved folder structure."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_file = sub.add_parser("file", help="Convert one Office file to PDF.")
    p_file.add_argument("--input", required=True, help="Path to one Office file.")
    p_file.add_argument("--input-root", help="Optional base folder used to preserve relative structure.")
    p_file.add_argument("--output-dir", help="Override output directory.")
    p_file.add_argument("--post-crop", choices=["none", "16:9", "a-series"], default="none", help="Optional centered crop for PowerPoint exports after conversion.")
    p_file.add_argument("--post-scale-percent", type=float, default=100.0, help="Optional centered content scale for PowerPoint exports after conversion, for example 98.")

    p_batch = sub.add_parser("batch", help="Convert Office files from input or from a custom folder.")
    p_batch.add_argument("--input-dir", help="Override input directory.")
    p_batch.add_argument("--output-dir", help="Override output directory.")
    p_batch.add_argument("--recursive", action="store_true", help="Scan subfolders recursively.")
    p_batch.add_argument("--extensions", help="Comma-separated extension filter, for example: docx,pptx,xlsx.")
    p_batch.add_argument("--post-crop", choices=["none", "16:9", "a-series"], default="none", help="Optional centered crop for PowerPoint exports after conversion.")
    p_batch.add_argument("--post-scale-percent", type=float, default=100.0, help="Optional centered content scale for PowerPoint exports after conversion, for example 98.")

    p_crop = sub.add_parser("crop-pptx", help="Crop PowerPoint-exported PDFs in output to exact 16:9.")
    p_crop.add_argument("--force", action="store_true", help="Crop again even if metadata says it was already cropped.")
    p_crop.add_argument("--output-dir", help="Override output directory.")

    p_pdf_split = sub.add_parser("pdf-split", help="Split PDFs from input into output.")
    p_pdf_split.add_argument("--input-dir", help="Override input PDF file or directory.")
    p_pdf_split.add_argument("--output-dir", help="Override output directory.")
    p_pdf_split.add_argument("--orientation", choices=["vertical", "horizontal"], required=True, help="Split direction: vertical left/right or horizontal top/bottom.")
    p_pdf_split.add_argument("--skip-cover", action="store_true", help="Keep the first and last pages unsplit.")

    p_pdf_crop = sub.add_parser("pdf-crop-margins", help="Crop PDF margins from input into output.")
    p_pdf_crop.add_argument("--input-dir", help="Override input PDF file or directory.")
    p_pdf_crop.add_argument("--output-dir", help="Override output directory.")
    p_pdf_crop.add_argument("--left-mm", type=float, default=0.0)
    p_pdf_crop.add_argument("--right-mm", type=float, default=0.0)
    p_pdf_crop.add_argument("--top-mm", type=float, default=0.0)
    p_pdf_crop.add_argument("--bottom-mm", type=float, default=0.0)

    p_pdf_aspect = sub.add_parser("pdf-crop-aspect", help="Crop PDFs from input into output to a target aspect ratio.")
    p_pdf_aspect.add_argument("--input-dir", help="Override input PDF file or directory.")
    p_pdf_aspect.add_argument("--output-dir", help="Override output directory.")
    p_pdf_aspect.add_argument("--mode", choices=["16:9", "a-series"], required=True)

    p_pdf_scale = sub.add_parser("pdf-scale-content", help="Scale PDF page contents from input into output without changing page size.")
    p_pdf_scale.add_argument("--input-dir", help="Override input PDF file or directory.")
    p_pdf_scale.add_argument("--output-dir", help="Override output directory.")
    p_pdf_scale.add_argument("--percent", type=float, required=True, help="Content scale percent, for example 98.")

    p_pdf_numbers = sub.add_parser("pdf-page-numbers", help="Add page numbers to PDFs from input into output.")
    p_pdf_numbers.add_argument("--input-dir", help="Override input PDF file or directory.")
    p_pdf_numbers.add_argument("--output-dir", help="Override output directory.")
    p_pdf_numbers.add_argument("--start-page", type=int, default=1, help="First physical page to receive a number.")
    p_pdf_numbers.add_argument("--start-number", type=int, default=1, help="Number printed on the first numbered page.")
    p_pdf_numbers.add_argument("--offset-mm", type=float, default=10.0, help="Distance from page edge in millimeters.")
    p_pdf_numbers.add_argument(
        "--position",
        choices=["bottom-left", "bottom-center", "bottom-right", "top-left", "top-center", "top-right"],
        default="bottom-right",
    )

    p_info = sub.add_parser("info", help="Print current settings and supported extensions.")
    p_info.add_argument("--lang", choices=["en", "ru"], default="en", help="Info output language.")
    return parser


def main() -> int:
    configure_stdio()
    root = Path(__file__).resolve().parents[1]
    ensure_dirs(root)

    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings(root)

    log_file = root / "logs" / f"run_{time.strftime('%Y%m%d_%H%M%S')}.log"
    log_message(log_file, f"Command: {' '.join(sys.argv)}")

    try:
        if args.command == "file":
            return cmd_file(
                root,
                log_file,
                args.input,
                args.input_root,
                args.output_dir,
                args.post_crop,
                args.post_scale_percent,
            )
        if args.command == "batch":
            return cmd_batch(
                root,
                log_file,
                args.input_dir,
                args.output_dir,
                args.recursive,
                args.extensions,
                args.post_crop,
                args.post_scale_percent,
            )
        if args.command == "crop-pptx":
            return cmd_crop_pptx(root, settings, log_file, force=args.force, output_dir=args.output_dir)
        if args.command == "pdf-split":
            return cmd_pdf_split(root, log_file, args.orientation, args.skip_cover, args.input_dir, args.output_dir)
        if args.command == "pdf-crop-margins":
            return cmd_pdf_crop_margins(
                root,
                log_file,
                args.left_mm,
                args.right_mm,
                args.top_mm,
                args.bottom_mm,
                args.input_dir,
                args.output_dir,
            )
        if args.command == "pdf-crop-aspect":
            return cmd_pdf_crop_aspect(root, log_file, args.mode, args.input_dir, args.output_dir)
        if args.command == "pdf-scale-content":
            return cmd_pdf_scale_content(root, log_file, args.percent, args.input_dir, args.output_dir)
        if args.command == "pdf-page-numbers":
            return cmd_pdf_page_numbers(
                root,
                log_file,
                args.start_page,
                args.start_number,
                args.offset_mm,
                args.position,
                args.input_dir,
                args.output_dir,
            )
        if args.command == "info":
            return cmd_info(root, settings, language=args.lang)
        raise ConversionError(f"Unknown command: {args.command}")
    except ConversionError as exc:
        log_message(log_file, f"ERROR: {exc}")
        print(f"[ERROR] {exc}")
        return 1
    except Exception as exc:
        log_message(log_file, f"UNHANDLED ERROR: {exc}")
        print(f"[ERROR] Unhandled failure: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
