from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from system_core import main
from system_core.ui_nicegui import app


def make_pdf(path: Path, *, width: float = 200, height: float = 100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    with path.open("wb") as stream:
        writer.write(stream)


def test_pdf_command_routes_single_file_to_custom_target(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    target = tmp_path / "result"
    make_pdf(source)

    result = main.cmd_pdf_split(
        tmp_path,
        tmp_path / "run.log",
        "vertical",
        input_dir=str(source),
        output_dir=str(target),
    )

    output = target / "source_split_vertical.pdf"
    assert result == 0
    assert output.is_file()
    assert len(PdfReader(str(output)).pages) == 2


def test_pdf_parser_accepts_explicit_routes() -> None:
    args = main.build_parser().parse_args(
        [
            "pdf-scale-content",
            "--percent",
            "98",
            "--input-dir",
            "D:/source.pdf",
            "--output-dir",
            "E:/target",
        ]
    )

    assert args.input_dir == "D:/source.pdf"
    assert args.output_dir == "E:/target"


def test_external_target_metadata_round_trip_keeps_relative_path(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_root = tmp_path / "external-target"
    pdf = output_root / "nested" / "slides.pdf"
    make_pdf(pdf)
    payload = {"source_family": "powerpoint", "cropped_exact_16_9": False}

    main.write_metadata_payload(project_root, pdf, payload, output_root)

    assert main.read_pdf_metadata(project_root, pdf, output_root) == payload
    assert (project_root / "report" / "latest" / "metadata" / "nested" / "slides.pdf.audion.json").is_file()


def test_gui_builds_single_file_command_without_staging(tmp_path: Path) -> None:
    source = tmp_path / "report.docx"
    target = tmp_path / "pdf"
    source.write_bytes(b"placeholder")

    command = app.build_convert_command(
        str(source),
        str(target),
        {"formats": ["docx"]},
        post_scale_percent=98,
    )

    assert "file" in command
    assert command[command.index("--input") + 1] == str(source.resolve())
    assert command[command.index("--output-dir") + 1] == str(target.resolve())
    assert "--post-scale-percent" in command
    assert "convert_cache" not in " ".join(command)


def test_gui_builds_batch_command_for_folder(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()

    command = app.build_convert_command(str(source), str(target), {"formats": ["pptx"]})

    assert "batch" in command
    assert "--recursive" in command
    assert command[command.index("--input-dir") + 1] == str(source.resolve())
    assert command[command.index("--output-dir") + 1] == str(target.resolve())


def test_workspace_delete_rejects_project_and_filesystem_roots() -> None:
    with pytest.raises(RuntimeError):
        app.validate_workspace_delete_target(app.ROOT)
    with pytest.raises(RuntimeError):
        app.validate_workspace_delete_target(Path(app.ROOT.anchor))


def test_non_loopback_gui_host_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDION_ALLOW_REMOTE_GUI", raising=False)
    with pytest.raises(SystemExit):
        app.assert_gui_host_allowed("0.0.0.0")
