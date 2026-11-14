FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git docker-cli && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/pyproject.toml backend/requirements.lock ./
COPY backend/app ./app
RUN pip install --no-cache-dir -c requirements.lock .
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY demo /app/demo
COPY benchmarks/fixtures /app/benchmarks/fixtures
EXPOSE 8010
CMD ["sh", "-c", "python /app/demo/prepare.py && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 1"]
