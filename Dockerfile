FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

# Create non-root user
RUN useradd -m -u 1000 parser && \
    mkdir -p /app /app/data /app/logs /app/session && \
    chown -R parser:parser /app

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=parser:parser parser_daemon.py .

# Switch to non-root user
USER parser

# Default command (can be overridden in docker-compose)
CMD ["python", "parser_daemon.py"]