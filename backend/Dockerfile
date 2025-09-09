# Backend Dockerfile for Hello Siling Classify and Extract
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Configure Chinese mirrors for faster package installation
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager) using Chinese mirror directly
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Configure uv to use Chinese mirror and install Python dependencies
RUN uv sync --frozen --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8001

# Set environment variables
ENV PYTHONPATH=/app
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["uv", "run", "python", "-m", "app.main"]
