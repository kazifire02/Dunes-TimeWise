"""Production entry point for normal Python hosts such as Render."""

from app import app

if not app.secret_key:
    raise RuntimeError("Set LATETRACK_SECRET_KEY before starting the server.")

app.config["SESSION_COOKIE_SECURE"] = True
