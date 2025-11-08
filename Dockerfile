# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership to app user
RUN chown -R app:app /app

# Expose port
EXPOSE 8000

# Development stage
FROM base as development

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    black \
    isort \
    flake8 \
    mypy \
    pytest-asyncio

# Switch to app user
USER app

# Run in development mode with reload
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "info"]

# Production stage
FROM base as production

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --loop uvloop"]
