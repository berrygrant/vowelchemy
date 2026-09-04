# Multi-stage build: compile the React UI, then ship a Python runtime that
# serves the API + the built SPA. No Node needed at runtime.
FROM node:20-slim AS ui
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# vite builds into ../src/vowelchemy/webui (i.e. /app/src/vowelchemy/webui here).
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
# Backend install (the acquisition tools MFA/new-fave/R are added by the user
# when needed — see the README). The freshly built UI is copied into the
# package before install so it ships inside site-packages.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY --from=ui /app/src/vowelchemy/webui ./src/vowelchemy/webui
RUN pip install --no-cache-dir .

EXPOSE 8000
ENV VOWELCHEMY_BROWSE_ROOT=/data
# Mount your corpora at /data (and set the browser confinement root to it).
CMD ["python", "-m", "uvicorn", "vowelchemy.api:app", "--host", "0.0.0.0", "--port", "8000"]
