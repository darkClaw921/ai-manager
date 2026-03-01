FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency file and install
COPY pyproject.toml .
RUN uv pip install --system .

# Copy application code
COPY bot/ bot/

EXPOSE 8443

CMD ["python", "-m", "bot.main"]
