FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml ./
COPY src/ ./src/
COPY pricing_maps/ ./pricing_maps/
COPY templates/ ./templates/

# Install the package in editable mode (no external network needed for runtime)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Create output directory
RUN mkdir -p /app/output

# Default command
ENTRYPOINT ["lakebase-assess"]
CMD ["--help"]
