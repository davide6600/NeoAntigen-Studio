FROM python:3.12.9-slim-bookworm

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip==25.0.1 && \
    pip install --no-cache-dir pydantic==2.10.6 pytest==8.3.4

COPY . .

CMD ["pytest", "-q"]
