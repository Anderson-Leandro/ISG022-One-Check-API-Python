"""IP e esquema do cliente atrás de proxies confiáveis (SEC-017, ADR-0015).

Cada proxy na frente da API acrescenta ao X-Forwarded-For o IP de quem o chamou. O que fica à
esquerda desses itens veio do cliente e pode ser forjado. Com PROXY_SALTOS=N proxies confiáveis, o
IP do cliente é o N-ésimo item a partir da direita. O uvicorn roda com --no-proxy-headers (start.sh)
para não trocar o client pelo primeiro item, e este middleware, o mais externo, faz a troca. Ele
também aplica o X-Forwarded-Proto do proxy, que o uvicorn deixou de ler, para que URLs montadas
pela aplicação (como o redirect da barra final) continuem em https.
"""

import ipaddress

from app.config import PROXY_SALTOS

_ESQUEMAS = {"http": {"http": "http", "https": "https"}, "websocket": {"http": "ws", "https": "wss"}}


def _so_ip(item: str) -> str:
    """Tira a porta (`1.2.3.4:5678`) e os colchetes do IPv6 (`[2001:db8::1]:443`)."""
    if item.startswith("["):
        return item[1 : item.find("]")] if "]" in item else item
    if item.count(":") == 1:
        return item.split(":", 1)[0]
    return item


def _itens(scope, nome: bytes) -> list[str]:
    """Itens de um cabeçalho de lista; várias linhas valem como uma só, na ordem (RFC 9110, 5.3)."""
    valores = ",".join(v.decode("latin-1") for k, v in scope.get("headers", []) if k == nome)
    return [i.strip() for i in valores.split(",")] if valores else []


def ip_do_cliente(cabecalho: str | None, ip_conexao: str | None, saltos: int) -> str | None:
    """IP do cliente pelo X-Forwarded-For, contando `saltos` proxies a partir da direita.

    Sem saltos, sem o cabeçalho, com menos itens que os saltos ou com item inválido, vale o IP da
    conexão: nunca um valor que o cliente possa escolher.
    """
    if saltos <= 0 or not cabecalho:
        return ip_conexao
    itens = [i.strip() for i in cabecalho.split(",")]
    if len(itens) < saltos:
        return ip_conexao
    try:
        return str(ipaddress.ip_address(_so_ip(itens[-saltos])))
    except ValueError:
        return ip_conexao


class IpClienteMiddleware:
    """Troca o client e o esquema do scope pelos que o proxy confiável informou."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # PROXY_SALTOS é o global deste módulo, lido a cada requisição: os testes trocam
        # app.ip_cliente.PROXY_SALTOS (trocar app.config.PROXY_SALTOS não tem efeito aqui)
        if scope["type"] in _ESQUEMAS and PROXY_SALTOS > 0:
            novo = {}
            cliente = scope.get("client")
            ip = ip_do_cliente(
                ",".join(_itens(scope, b"x-forwarded-for")), cliente[0] if cliente else None, PROXY_SALTOS
            )
            if ip and (not cliente or ip != cliente[0]):
                novo["client"] = (ip, cliente[1] if cliente else 0)
            # o último item é o do proxy mais próximo; outro valor que não http/https é ignorado
            proto = _itens(scope, b"x-forwarded-proto")
            esquema = _ESQUEMAS[scope["type"]].get(proto[-1].lower()) if proto else None
            if esquema and esquema != scope.get("scheme"):
                novo["scheme"] = esquema
            if novo:
                scope = {**scope, **novo}
        await self.app(scope, receive, send)
