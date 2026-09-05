FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models HF_HUB_DISABLE_TELEMETRY=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home caption \
    && mkdir /models && chown caption:caption /models
WORKDIR /app
COPY requirements-linux.lock .
RUN pip install --no-cache-dir -r requirements-linux.lock
COPY server.py api_compat.py healthcheck.py ./
COPY static/ static/
COPY LICENSE .
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=10s --timeout=5s --start-period=300s --retries=3 \
    CMD python healthcheck.py
ENTRYPOINT ["python", "server.py"]
CMD ["--host", "0.0.0.0"]
