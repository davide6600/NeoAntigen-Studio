FROM python:3.12.9-slim-bookworm

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip==25.0.1 && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir celery==5.4.0 redis==5.2.1 boto3==1.35.92 psycopg[binary]==3.2.3

COPY . .

ENV PYTHONUNBUFFERED=1
