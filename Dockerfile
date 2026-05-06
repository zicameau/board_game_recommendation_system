# Production image — MODEL_VERSION selects one bundle subdirectory under bundles/
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic/
COPY app ./app/
COPY scripts ./scripts/

ARG MODEL_VERSION=popularity-v1-fixture
ENV MODEL_VERSION=${MODEL_VERSION}
ENV MODEL_BUNDLE_PATH=/app/bundles

COPY bundles/${MODEL_VERSION} ./bundles/${MODEL_VERSION}/

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

RUN touch /app/.env.local

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
