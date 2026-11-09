"""Dados de contexto da trilha de auditoria (log_operacao): IP de origem e campos alterados.

O IP vem de uma ContextVar preenchida por middleware, para que as rotas não
precisem repassar o Request a cada chamada de log_operacao. Atrás do proxy do
Render, o uvicorn já troca o client pelo X-Forwarded-For (FORWARDED_ALLOW_IPS).
"""

import hashlib
import hmac
from contextvars import ContextVar

from sqlalchemy import inspect

from app.config import JWT_SECRET

_ip_requisicao: ContextVar[str | None] = ContextVar("ip_requisicao", default=None)


def ip_atual() -> str | None:
    """IP do cliente da requisição em andamento; None fora de uma requisição (scripts, seed)."""
    return _ip_requisicao.get()


def email_para_log(digitado: str) -> str:
    """Identificador do e-mail digitado num login falho, sem o texto (SEC-019).

    O campo pode trazer uma senha digitada no lugar errado, e até uma parte dela (o "domínio" de
    "Joao@Casa.net") seria vazamento. Um HMAC com o segredo do servidor não se reverte por dicionário
    sem a chave, e ainda junta as tentativas com o mesmo e-mail."""
    normalizado = digitado.strip().lower().encode()
    return hmac.new(JWT_SECRET.encode(), b"login_falho:" + normalizado, hashlib.sha256).hexdigest()[:16]


def campos_alterados(*objetos) -> list[str]:
    """Nomes das colunas alteradas e ainda não gravadas, sem os valores.

    Chamar antes do commit e de qualquer consulta, que dispara o autoflush e zera o histórico.
    """
    nomes = set()
    for obj in objetos:
        estado = inspect(obj)
        for coluna in estado.mapper.column_attrs:
            if estado.attrs[coluna.key].history.has_changes():
                nomes.add(coluna.key)
    return sorted(nomes)


class IpRequisicaoMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cliente = scope.get("client")
        token = _ip_requisicao.set(cliente[0] if cliente else None)
        try:
            await self.app(scope, receive, send)
        finally:
            _ip_requisicao.reset(token)
