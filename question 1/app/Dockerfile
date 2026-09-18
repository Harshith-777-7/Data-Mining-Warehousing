FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache DuckDB extensions inside the Docker image for 100% offline cold-start reliability
RUN python -c "import duckdb; con = duckdb.connect(); con.install_extension('httpfs'); con.install_extension('postgres')"

# Copy application files
COPY . .

# Set permissions for entrypoint
RUN chmod +x entrypoint.sh run_all.py

EXPOSE 8501

ENTRYPOINT ["./entrypoint.sh"]
