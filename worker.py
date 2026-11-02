"""Cloudflare entry point. Run the normal Flask app through the WSGI adapter."""

from jinja2 import DictLoader
from workers import WorkerEntrypoint, Response, wsgi

from app import app
from bundled_templates import TEMPLATES

app.jinja_loader = DictLoader(TEMPLATES)
app.config["SESSION_COOKIE_SECURE"] = True


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        # Each request opens and closes its own database connections. Never
        # retain sockets or request I/O in global state across Worker requests.
        secret = getattr(self.env, "LATETRACK_SECRET_KEY", None)
        if not secret:
            return Response("Set the LATETRACK_SECRET_KEY runtime secret.", status=503)
        app.secret_key = str(secret)
        return await wsgi.fetch(app, request, self.env, self.ctx)
