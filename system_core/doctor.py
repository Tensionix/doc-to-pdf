from __future__ import annotations

from pathlib import Path
import importlib
import os
import platform
import shutil
import subprocess
import sys


REQUIRED_MODULES = [
    ("pypdf", "pypdf"),
]


def check_module(import_name: str) -> tuple[bool, str]:
    try:
        mod = importlib.import_module(import_name)
        version = getattr(mod, "__version__", "unknown")
        return True, str(version)
    except Exception as exc:
        return False, exc.__class__.__name__


def detect_python_mode(root: Path) -> str:
    if (root / "runtime" / "python.exe").exists():
        return "portable-runtime"
    if (root / "runtime" / "python" / "python.exe").exists():
        return "portable-runtime"
    return "system-python"


def find_powershell(root: Path) -> str | None:
    candidates = [
        root / "system_core" / "powershell" / "pwsh.exe",
        Path(shutil.which("pwsh") or ""),
        Path(shutil.which("powershell") or ""),
        Path(shutil.which("powershell.exe") or ""),
    ]
    for item in candidates:
        if str(item) and item.exists():
            return str(item)
    return None


def check_office_com(prog_id: str) -> bool:
    if platform.system() != "Windows":
        return False

    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps:
        return False

    cmd = [
        ps,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        f"try {{ New-Object -ComObject {prog_id} | Out-Null; 'OK' }} catch {{ 'FAIL' }}",
    ]
    try:
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            env=env,
        )
        return "OK" in result.stdout
    except Exception:
        return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]

    print("======================================================================")
    print("AUDION DOC TO PDF - ENVIRONMENT DOCTOR")
    print("======================================================================")
    print(f"Project root : {root}")
    print(f"Executable   : {sys.executable}")
    print(f"Python       : {sys.version.split()[0]}")
    print(f"Python mode  : {detect_python_mode(root)}")
    print(f"Platform     : {platform.platform()}")
    print()

    failed = False

    print("[Required modules]")
    for import_name, package_name in REQUIRED_MODULES:
        ok, detail = check_module(import_name)
        status = "OK" if ok else "FAIL"
        print(f"  - {package_name:<18} : {status:<4} {detail}")
        if not ok:
            failed = True

    print()
    print("[Tooling]")
    powershell = find_powershell(root)
    print(f"  - powershell         : {'OK' if powershell else 'MISS'} {powershell or 'not found'}")
    print(f"  - word com           : {'OK' if check_office_com('Word.Application') else 'MISS'}")
    print(f"  - excel com          : {'OK' if check_office_com('Excel.Application') else 'MISS'}")
    print(f"  - powerpoint com     : {'OK' if check_office_com('PowerPoint.Application') else 'MISS'}")

    print()
    if failed:
        print("[RESULT] One or more required Python modules are missing.")
        return 1

    print("[RESULT] Required environment looks good.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
