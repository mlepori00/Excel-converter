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

EXPOSE 8000
CMD ["uvicorn", "offerten_converter.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
