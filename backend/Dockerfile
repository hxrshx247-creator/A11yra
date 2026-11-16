FROM node:24-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
COPY backend/app/product/plan_prices.json /app/backend/app/product/plan_prices.json
ENV VITE_TEMPORARY_DEMO=true
RUN npm run build

FROM python:3.12-slim AS api
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer poppler-utils fonts-crosextra-carlito fonts-crosextra-caladea fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY reader/ reader/
RUN useradd --system --uid 10001 a11yra \
    && mkdir -p /app/backend/.a11yra-data \
    && chown -R a11yra:a11yra /app
USER a11yra
WORKDIR /app/backend
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --workers 1 --no-access-log"]

FROM api AS demo
COPY --from=frontend /app/frontend/dist /app/frontend/dist
ENV A11YRA_FRONTEND_DIR=/app/frontend/dist
