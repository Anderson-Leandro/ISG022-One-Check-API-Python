"""Cabeçalhos de segurança em todas as respostas, inclusive erros gerados por outros middlewares.

As respostas da API trazem dados pessoais e tokens: não podem ficar em cache do
navegador ou de proxies, nem ser interpretadas como outro tipo ou embutidas em
frames de outros sites.
"""
from app.config import IS_DEV

# As fotos são públicas e imutáveis (nome aleatório): podem ficar em cache
_COM_CACHE = "/api/v1/uploads/"

_BASICOS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
]
# Em desenvolvimento a API roda em http://localhost: HSTS só atrapalharia
_HSTS = [] if IS_DEV else [(b"strict-transport-security", b"max-age=31536000")]


class CabecalhosSegurancaMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        extras = _BASICOS + _HSTS
        if not scope["path"].startswith(_COM_CACHE):
            extras = extras + [(b"cache-control", b"no-store")]

        async def send_com_cabecalhos(mensagem):
            if mensagem["type"] == "http.response.start":
                headers = list(mensagem.get("headers", []))
                existentes = {nome.lower() for nome, _ in headers}
                # Não sobrescreve o que a rota definiu (ex.: a CSP das fotos)
                headers += [(nome, valor) for nome, valor in extras if nome not in existentes]
                mensagem = {**mensagem, "headers": headers}
            await send(mensagem)

        await self.app(scope, receive, send_com_cabecalhos)
