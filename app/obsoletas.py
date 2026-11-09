"""Rotas obsoletas (DEBT-003, ADR-0013): continuam funcionando até a data de remoção, avisando quem chama.

A tabela ROTAS é a única fonte: `marcar_no_openapi` põe deprecated=True e a data na descrição de cada
rota dela no OpenAPI gerado, e o middleware põe em toda resposta delas, inclusive 401 e 403:
  - Deprecation (RFC 9745): desde quando a rota está obsoleta;
  - Sunset (RFC 8594): a partir de quando ela pode deixar de existir;
  - Link rel="successor-version": a URL da rota canônica, quando ela não depende do corpo. O método da
    sucessora, que pode ser outro, está na descrição do OpenAPI.
"""

import re
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import NamedTuple
from urllib.parse import quote

DESDE = datetime(2026, 11, 8, tzinfo=UTC)
REMOCAO = datetime(2027, 1, 31, tzinfo=UTC)
PREFIXO = "/api/v1"


class Obsoleta(NamedTuple):
    metodo: str
    caminho: str  # como declarado no router, depois do prefixo; {usuario_id} é o id da URL
    sucessora: str  # "MÉTODO /caminho"
    link: bool = True  # False quando a URL da sucessora depende do corpo da requisição


ROTAS = [
    Obsoleta("POST", "/usuarios/me/mfa/setup", "POST /auth/mfa/setup"),
    Obsoleta("POST", "/usuarios/me/mfa/enable", "POST /auth/mfa/activate"),
    Obsoleta("DELETE", "/usuarios/me/mfa", "POST /auth/mfa/desabilitar"),
    Obsoleta("POST", "/usuarios/{usuario_id}/mfa/habilitar", "POST /usuarios/{usuario_id}/mfa/enable"),
    Obsoleta("POST", "/usuarios/{usuario_id}/mfa/desabilitar", "DELETE /usuarios/{usuario_id}/mfa"),
    Obsoleta("POST", "/auth/mfa/disable", "DELETE /usuarios/{usuario_id}/mfa (usuario_id do corpo)", link=False),
]

# O id é um segmento qualquer, menos "me" (que é outra rota)
_ID = r"(?P<usuario_id>(?!me/)[^/]+)"
_PADROES = [
    (r, re.compile("^" + re.escape(PREFIXO + r.caminho).replace(re.escape("{usuario_id}"), _ID) + "/?$")) for r in ROTAS
]


def descricao(rota: Obsoleta) -> str:
    return f"Obsoleta: removida a partir de {REMOCAO:%Y-%m-%d}. Use {rota.sucessora}."


def marcar_no_openapi(app) -> None:
    """deprecated=True e a descrição de cada rota da tabela no OpenAPI gerado.

    Falha ao gerar o OpenAPI se a tabela citar uma rota que não existe."""
    gerar = app.openapi

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = gerar()
        faltando = []
        for rota in ROTAS:
            operacao = schema.get("paths", {}).get(PREFIXO + rota.caminho, {}).get(rota.metodo.lower())
            if operacao is None:
                faltando.append(f"{rota.metodo} {rota.caminho}")
                continue
            operacao["deprecated"] = True
            operacao["description"] = descricao(rota)
        if faltando:
            raise RuntimeError(f"Rotas obsoletas sem rota correspondente: {faltando}")
        return schema

    app.openapi = openapi


def sucessora(metodo: str, caminho: str) -> tuple[Obsoleta, str | None] | None:
    """(rota obsoleta, URL da sucessora para o Link) de uma requisição; None se ela não é obsoleta."""
    for rota, padrao in _PADROES:
        if rota.metodo != metodo:
            continue
        achado = padrao.match(caminho)
        if achado:
            if not rota.link:
                return rota, None
            url = rota.sucessora.split(" ", 1)[1]
            if "{usuario_id}" in url:
                url = url.replace("{usuario_id}", quote(achado.group("usuario_id"), safe=""))
            return rota, PREFIXO + url
    return None


_CABECALHOS_FIXOS = [
    (b"deprecation", f"@{int(DESDE.timestamp())}".encode()),
    (b"sunset", format_datetime(REMOCAO, usegmt=True).encode()),
]


class RotasObsoletasMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        achado = sucessora(scope["method"], scope["path"]) if scope["type"] == "http" else None
        if not achado:
            return await self.app(scope, receive, send)

        extras = list(_CABECALHOS_FIXOS)
        if achado[1]:
            extras.append((b"link", f'<{achado[1]}>; rel="successor-version"'.encode()))

        async def send_com_aviso(mensagem):
            if mensagem["type"] == "http.response.start":
                mensagem = {**mensagem, "headers": list(mensagem.get("headers", [])) + extras}
            await send(mensagem)

        await self.app(scope, receive, send_com_aviso)
