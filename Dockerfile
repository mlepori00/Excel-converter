# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# System dependencies required for headless Camoufox (Firefox-based market price scraper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fonts-liberation \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    libnss3 \
    libasound2 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PYTHONPATH=/app/src
# Containers run in production mode → a missing SECRET_KEY fails fast (see config.py).
ENV APP_ENV=production

# Drop root: the app parses untrusted supplier files in-process (openpyxl/pandas/xlrd),
# so don't run those parsers as UID 0. appuser owns /app incl. the data dir/volume.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

# Download Camoufox browser binary into appuser's home so StealthyFetcher can find it.
# Runs as appuser (not root) so the path matches runtime. Fails gracefully if unavailable.
RUN python -m camoufox fetch || echo "Camoufox fetch skipped – market price scraper will be disabled"

EXPOSE 8000

# Liveness probe against the app's /health route. Uses stdlib urllib (no curl in
# the slim image). A hung-but-alive uvicorn turns unhealthy and is restarted by
# the orchestrator (compose: restart: unless-stopped).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "offerten_converter.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
