FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Versões e hashes travados: o build falha se algum pacote baixado for diferente (SEC-006).
# --only-binary: só wheels, nenhum setup.py roda no build e a imagem não precisa de gcc (SEC-008)
COPY requirements.lock .
RUN pip install --require-hashes --only-binary=:all: -r requirements.lock

# Usuário sem privilégio: o código fica com dono root (só leitura para a API); só uploads é gravável
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p uploads && chown app:app uploads && chmod 750 uploads

COPY app ./app
COPY scripts ./scripts
COPY start.sh ./start.sh
RUN chmod 755 start.sh

USER app
EXPOSE 8000

CMD ["bash", "start.sh"]
