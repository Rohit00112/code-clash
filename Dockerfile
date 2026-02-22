FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Runtime toolchains used by the code executor (Python, JS, Java, C/C++, C#).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    default-jdk \
    nodejs \
    npm \
    mono-devel \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

COPY backend /app/backend
COPY questions /app/questions
COPY testcases /app/testcases

RUN mkdir -p /app/temp /app/logs /app/exports && \
    useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Run migrations first, then start API (embedded worker is enabled by env config).
CMD ["sh", "-c", "alembic upgrade head && python run.py"]
