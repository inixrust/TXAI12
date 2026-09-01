# Image aplikasi TX-AI12: Streamlit + ragcore, plus Java 17 + SQLcl untuk server
# MCP Oracle (tab Agent/Konsultasi). Mengontainerkan app menghapus "lompatan ke
# host": Caddy -> app dan app -> OpenBao/DB kini container->container di jaringan
# Docker, jadi tak ada lagi ganjalan Windows Firewall / host.docker.internal.
#
# Optional BERAT sengaja dilewati agar image ramping & cepat dibangun:
#   - sentence-transformers (reranker, tarik torch ~2 GB) - app jalan tanpanya.
#   - pytesseract (OCR pembanding) - lapis 2 ekstraksi dilewati sendiri bila absen.
#
#   docker build -f infra/Dockerfile -t txai12-app:latest .
FROM python:3.11-slim

# JRE default distro (SQLcl -mcp WAJIB Java 17+; Debian trixie kini menyediakan
# 21, tetap memenuhi) + unzip/curl untuk memasang SQLcl.
RUN apt-get update && apt-get install -y --no-install-recommends \
      default-jre-headless curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# SQLcl - server MCP Oracle. Diunduh dari Oracle (SQLcl tak butuh login).
# Dipisah sebagai layer sendiri supaya cache build tetap berguna.
ARG SQLCL_URL=https://download.oracle.com/otn_software/java/sqldeveloper/sqlcl-latest.zip
RUN curl -fsSL "$SQLCL_URL" -o /tmp/sqlcl.zip \
    && unzip -q /tmp/sqlcl.zip -d /opt \
    && rm /tmp/sqlcl.zip
ENV SQLCL_HOME=/opt/sqlcl

WORKDIR /app

# Deps Python - lewati optional berat (lihat catatan di atas).
COPY requirements.txt .
RUN grep -vE '^(sentence-transformers|pytesseract)' requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

# Kode + config Streamlit (maxUploadSize dsb).
COPY src/ ./src/
COPY apps/ ./apps/
COPY .streamlit/ ./.streamlit/
ENV PYTHONPATH=/app/src

# Non-root.
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8501
# server.address 0.0.0.0 supaya terjangkau Caddy dari jaringan Docker.
CMD ["python", "-m", "streamlit", "run", "apps/app12.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
