"""PostgreSQL connections for local Flask and Cloudflare Python Workers."""

import os
import ssl
from urllib.parse import parse_qs, unquote, urlsplit

import pg8000.dbapi
from flask import has_request_context, request


def setting(name, default=None):
    if has_request_context():
        env = request.environ.get("workers.env")
        value = env.get(name) if isinstance(env, dict) else getattr(env, name, None)
        if value is not None:
            return value
    return os.environ.get(name, default)


class DictCursor(pg8000.dbapi.Cursor):
    """Keep PostgreSQL dates/numbers native while returning named columns."""

    def __next__(self):
        row = super().__next__()
        return dict(zip((column[0] for column in self.description), row))


def dict_cursor(connection):
    from neon_http import NeonConnection
    if isinstance(connection, NeonConnection):
        return connection.cursor()
    return DictCursor(connection)


def connect_url(url):
    """Connect with verified TLS; URLs are supplied through secrets, never source."""
    parsed = urlsplit(url)
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
        raise ValueError("Provide a valid PostgreSQL DATABASE_URL.")
    options = parse_qs(parsed.query)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    sslmode = options.get("sslmode", ["verify-full"])[0]
    if sslmode == "disable" and not local:
        raise ValueError("TLS may only be disabled for a local test database.")
    if sslmode not in ("require", "verify-ca", "verify-full", "disable"):
        raise ValueError("Use sslmode=require or sslmode=verify-full.")
    context = False if sslmode == "disable" else ssl.create_default_context()
    connection = pg8000.dbapi.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=unquote(parsed.path.lstrip("/")),
        ssl_context=context,
        timeout=int(options.get("connect_timeout", ["15"])[0]),
        application_name="dunes-timewise",
    )
    # pg8000 negotiates SCRAM channel binding automatically. Honor a URL that
    # explicitly requires it rather than silently accepting weaker negotiation.
    if options.get("channel_binding", [""])[0] == "require":
        mechanism = getattr(getattr(connection, "auth", None), "mechanism_name", "")
        if not mechanism.endswith("-PLUS"):
            connection.close()
            raise ValueError("Server did not negotiate the required SCRAM channel binding.")
    return connection


def get_connection():
    url = setting("DATABASE_URL_POOLED") or setting("DATABASE_URL")
    if url and has_request_context() and request.environ.get("workers.env") is not None:
        from neon_http import NeonConnection
        return NeonConnection(str(url))
    hyperdrive = setting("HYPERDRIVE")
    if hyperdrive is not None:
        # Hyperdrive provides the secure Worker-side connection and handles TLS
        # to Neon. Never use ssl_context=False for a direct Internet connection.
        return pg8000.dbapi.connect(
            host=hyperdrive.host,
            port=int(hyperdrive.port),
            user=hyperdrive.user,
            password=hyperdrive.password,
            database=hyperdrive.database,
            ssl_context=False,
            timeout=15,
            tcp_keepalive=False,
        )
    url = setting("DATABASE_URL_POOLED") or setting("DATABASE_URL")
    if not url:
        raise RuntimeError("Set DATABASE_URL_POOLED or add a HYPERDRIVE binding.")
    return connect_url(str(url))
