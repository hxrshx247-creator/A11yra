FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000
WORKDIR /app
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
