FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (from service requirements)
COPY services/auth_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library
COPY shared /app/shared

# Copy service code
COPY services/auth_service /app/services/auth_service

# Empty __init__ for services package
RUN touch /app/services/__init__.py

# Set PYTHONPATH so shared/ and services/ are importable
ENV PYTHONPATH=/app

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "services.auth_service.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
