FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Versões e hashes travados: o build falha se algum pacote baixado for diferente (SEC-006)
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY app ./app
COPY scripts ./scripts
COPY start.sh ./start.sh
RUN chmod +x start.sh

RUN mkdir -p uploads

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["bash", "start.sh"]
