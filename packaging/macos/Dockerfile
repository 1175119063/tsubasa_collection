FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TSUBASA_DATA_DIR=/app/data

WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
RUN python -m pip install --no-cache-dir .

RUN mkdir -p /app/data/photos /app/data/thumbnails /app/data/audio /app/data/.tmp
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
