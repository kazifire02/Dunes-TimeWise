"""Fail the build before upload if required Python runtime packages are absent."""

from pathlib import Path


def verify(root):
    vendor = root / "python_modules"
    required = ("jinja2", "flask", "werkzeug", "markupsafe", "pg8000", "openpyxl", "Crypto", "workers")
    missing = [name for name in required if not (vendor / name / "__init__.py").is_file()]
    if missing:
        raise SystemExit(
            "Worker runtime packages are missing: " + ", ".join(missing)
            + ". Run uv run pywrangler sync --force before deployment."
        )
    print("Verified Worker runtime packages: " + ", ".join(required))


if __name__ == "__main__":
    verify(Path(__file__).resolve().parents[1])
