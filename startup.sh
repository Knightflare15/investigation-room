#!/bin/sh
exec gunicorn -k uvicorn.workers.UvicornWorker -w "${GUNICORN_WORKERS:-2}" -b "0.0.0.0:${PORT:-8000}" backend.app.main:app
