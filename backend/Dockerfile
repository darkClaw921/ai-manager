FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy all source code
COPY pyproject.toml .
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

# Install CPU-only PyTorch first (saves ~3GB by excluding NVIDIA CUDA packages)
RUN uv pip install --system torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies (non-editable to avoid hatchling issues in container)
RUN uv pip install --system .

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
