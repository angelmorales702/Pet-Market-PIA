FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar configuración de dependencias e instalar
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .[dev]

# Copiar código de aplicación y tests
COPY src/ ./src/
COPY tests/ ./tests/
COPY docs/ ./docs/

# Exponer puerto predeterminado
EXPOSE 8000

# Health check para Render / Fly.io / Railway
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
