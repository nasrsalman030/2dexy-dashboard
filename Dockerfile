FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask==3.0.3 flask-cors==4.0.0 gunicorn==22.0.0

WORKDIR /app

COPY index.html .
COPY server.py .

RUN mkdir -p /data

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/2dexy.db

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "server:app"]
