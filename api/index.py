"""Vercel serverless entrypoint — wraps the Flask app.

Vercel's Python runtime calls `handler(req, context)`. We translate the
incoming request into a WSGI environ, run the Flask app, and return the
WSGI response as (status, headers, body).
"""
import io
import os
import sys

# Make project modules importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a temp DB so the serverless filesystem (read-only) doesn't break rooms
os.environ.setdefault("DIRTYTRUTH_DB", "/tmp/dirtytruth_rooms.db")

from app import app  # noqa: E402


def handler(req, context):
    # Build WSGI environ from the Vercel request
    body = req.body or b""
    environ = {
        "REQUEST_METHOD": req.method,
        "PATH_INFO": req.path,
        "QUERY_STRING": req.query_string or "",
        "SERVER_NAME": req.headers.get("host", "localhost").split(":")[0],
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.input": io.BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.url_scheme": "https",
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": req.headers.get("content-type", ""),
    }
    for key, value in req.headers.items():
        k = key.upper().replace("-", "_")
        if k not in ("CONTENT_LENGTH", "CONTENT_TYPE"):
            environ["HTTP_" + k] = value

    # Capture the WSGI response
    status_parts = []
    headers_list = []

    def start_response(status, headers, exc_info=None):
        status_parts.append(status)
        headers_list.extend(headers)

    chunks = app.wsgi_app(environ, start_response)
    data = b"".join(chunks)

    status_code = int(status_parts[0].split(" ", 1)[0]) if status_parts else 500
    return status_code, headers_list, data
