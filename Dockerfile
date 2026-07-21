# Multi-stage build: compile the React UI, then ship a Python runtime that
# serves the API + the built SPA. No Node needed at runtime.
FROM node:20-slim AS ui
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
# Backend install (the acquisition tools MFA/new-fave/R are added by the user
# when needed — see the README).
COPY pyproject.toml README.md ./
COPY vowelchemy/ ./vowelchemy/
RUN pip install --no-cache-dir .
# Bring in the prebuilt UI so `vowelchemy app` serves it.
COPY --from=ui /app/frontend/dist ./frontend/dist

EXPOSE 8000
ENV VOWELCHEMY_BROWSE_ROOT=/data
# Mount your corpora at /data (and set the browser confinement root to it).
CMD ["python", "-m", "uvicorn", "vowelchemy.api:app", "--host", "0.0.0.0", "--port", "8000"]
