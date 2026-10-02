FROM python:3.12-slim
WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server /app/server
COPY nexus/ed25519.py /app/server/ed25519.py
ENV NEXUS_DB=/data/nexus_online.db
RUN mkdir -p /data
EXPOSE 8000
# hosts like Railway/Render tell the app its port through $PORT
CMD ["sh", "-c", "python -m uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
