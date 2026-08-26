import os
import subprocess
from pathlib import Path

def office_to_pdf(source: Path, output_dir: Path, timeout: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = "/tmp"

    cmd = [
        "libreoffice",
        "--headless",
        "--nologo",
        "--nodefault",
        "--nofirststartwizard",
        "--norestore",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(source),
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("محرك LibreOffice غير مثبت على الخادم.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("استغرق التحويل وقتًا أطول من المسموح.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("فشل محرك Office في تحويل الملف.") from exc

    produced = output_dir / f"{source.stem}.pdf"
    if not produced.exists() or produced.stat().st_size == 0:
        raise RuntimeError("لم يُنتج LibreOffice ملف PDF صالحًا.")
    return produced
