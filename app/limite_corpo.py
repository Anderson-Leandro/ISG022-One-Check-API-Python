"""Limite de tamanho do corpo das requisições, aplicado antes do roteamento e da autenticação.

Sem ele, o FastAPI lê e grava em disco o corpo inteiro (inclusive multipart de
vários GB) antes de qualquer dependência rodar, então um anônimo conseguia
consumir disco e CPU mesmo recebendo 401 no fim.
"""
import json

from starlette.exceptions import HTTPException

from app.config import MAX_BODY_KB, MAX_UPLOAD_MB

# Folga para os demais campos e cabeçalhos das partes do multipart
LIMITE_MULTIPART = (MAX_UPLOAD_MB + 1) * 1024 * 1024
LIMITE_PADRAO = MAX_BODY_KB * 1024


class CorpoGrandeDemais(HTTPException):
    """HTTPException para o FastAPI repassar como 413 em vez de convertê-la em erro 400 de parsing."""

    def __init__(self, limite: int):
        super().__init__(status_code=413, detail=_mensagem_413(limite))


class LimiteCorpoMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope["headers"])
        tipo = headers.get(b"content-type", b"").decode("latin-1").lower()
        limite = LIMITE_MULTIPART if tipo.startswith("multipart/") else LIMITE_PADRAO

        tamanho = headers.get(b"content-length")
        if tamanho is not None:
            try:
                if int(tamanho) > limite:
                    return await _responder_413(send, limite)
            except ValueError:
                return await _responder(send, 400, "Content-Length inválido")

        # Corpo sem Content-Length (chunked) ou que não respeita o valor declarado: conta ao ler
        recebido = 0
        resposta_iniciada = False

        async def receive_limitado():
            nonlocal recebido
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebido += len(mensagem.get("body", b""))
                if recebido > limite:
                    raise CorpoGrandeDemais(limite)
            return mensagem

        async def send_monitorado(mensagem):
            nonlocal resposta_iniciada
            if mensagem["type"] == "http.response.start":
                resposta_iniciada = True
            await send(mensagem)

        try:
            await self.app(scope, receive_limitado, send_monitorado)
        except CorpoGrandeDemais:
            if not resposta_iniciada:
                await _responder_413(send, limite)


def _mensagem_413(limite: int) -> str:
    return f"Requisição excede o limite de {limite // 1024} KB"


async def _responder_413(send, limite: int) -> None:
    await _responder(send, 413, _mensagem_413(limite))


async def _responder(send, status: int, detail: str) -> None:
    # Mesmo formato das HTTPException da API (401, 403, 429)
    corpo = json.dumps({"detail": detail}, ensure_ascii=False).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(corpo)).encode()), (b"connection", b"close")],
    })
    await send({"type": "http.response.body", "body": corpo})
