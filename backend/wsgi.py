"""WSGI entrypoint. Gunicorn is pointed at `app:app` directly (see Dockerfile),
but this module is kept for clarity / alternate entrypoints (`wsgi:app`)."""

from app import app

if __name__ == "__main__":
    app.run()
