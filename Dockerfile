# ── Stage 1: Build ──
FROM python:3.11-slim AS builder

LABEL maintainer="CRISPR Target Finder Team"
LABEL description="Production CRISPR/Cas9 gRNA design & analysis tool"
LABEL version="1.0.0"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN groupadd -r crispr && useradd -r -g crispr -d /app -s /sbin/nologin crispr

# Copy Python packages from builder
COPY --from=builder /root/.local /home/crispr/.local
ENV PATH="/home/crispr/.local/bin:${PATH}"
ENV PYTHONPATH="/app"

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /app/user_data && chown -R crispr:crispr /app

USER crispr

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "main.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
