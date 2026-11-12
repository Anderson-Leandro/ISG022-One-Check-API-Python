"""Senhas que aparecem em vazamentos conhecidos (SEC-030), pelo Have I Been Pwned.

Decisão do PO em 2026-11-11:
- k-anonymity: só os 5 primeiros caracteres do SHA-1 da senha saem da API; o serviço devolve os sufixos com
  esse começo, e a comparação é feita aqui. A senha e o hash completo nunca saem.
- Add-Padding: o serviço completa a resposta com sufixos falsos (contagem 0), para o tamanho dela não indicar
  o prefixo consultado. Linhas com contagem 0 não contam como vazamento.
- Prazo total de 2 s (inclusive o DNS) e fail open: se o serviço não responder no prazo, ou responder algo
  inesperado, a senha é aceita e o fato vai para o log, sem a senha nem o hash.
- SENHA_VAZADA_CONSULTA=false desliga a consulta (a conftest dos testes desliga; não há rede no CI).

A consulta é chamada nas rotas (exigir_senha_nao_vazada), não no schema: as rotas são síncronas e rodam numa
thread, fora do event loop, e a consulta só acontece depois da autorização e da conferência da senha atual.
Vale só para senhas novas, depois da política de app/senhas.py.
"""

import hashlib
import logging
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as PrazoEsgotado

from app.config import SENHA_VAZADA_CONSULTA
from app.schemas import fail

URL = "https://api.pwnedpasswords.com/range/"
TIMEOUT_S = 2
# A resposta tem cerca de 2 mil linhas de 40 bytes; bem mais que isso é uma resposta estranha
LIMITE_RESPOSTA = 256 * 1024
MENSAGEM = "Esta senha aparece em vazamentos conhecidos; escolha outra"

# Global do módulo, lido a cada chamada: os testes trocam app.senhas_vazadas.CONSULTA_ATIVA
CONSULTA_ATIVA = SENHA_VAZADA_CONSULTA

logger = logging.getLogger(__name__)
# Threads próprias dão o prazo total: o timeout do urlopen vale por operação de socket e não cobre o DNS
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="senhas-vazadas")


def _consultar_faixa(prefixo: str) -> str:
    """Os sufixos de SHA-1 que começam com `prefixo` (5 caracteres hexadecimais), no formato SUFIXO:CONTAGEM."""
    # A URL é fixa (https); o único pedaço variável é o prefixo do hash, nunca um valor vindo do usuário
    if not re.fullmatch(r"[0-9A-F]{5}", prefixo):
        raise ValueError("prefixo de SHA-1 inválido")
    req = urllib.request.Request(URL + prefixo, headers={"Add-Padding": "true", "User-Agent": "OneCheckAPI/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - URL fixa, https
        tipo = resp.headers.get("Content-Type", "")
        if resp.status != 200 or not tipo.startswith("text/plain"):
            raise ValueError(f"resposta inesperada ({resp.status}, {tipo})")
        corpo = resp.read(LIMITE_RESPOSTA + 1)
    if len(corpo) > LIMITE_RESPOSTA:
        raise ValueError("resposta grande demais")
    return corpo.decode("utf-8")


def senha_vazada(senha: str) -> bool:
    """True se a senha aparece na base de vazadas. Desligada ou sem resposta no prazo: False (fail open)."""
    if not CONSULTA_ATIVA:
        return False
    # SHA-1 é o formato do serviço, não uma proteção da senha: só o prefixo sai daqui
    sha1 = hashlib.sha1(senha.encode(), usedforsecurity=False).hexdigest().upper()
    prefixo, sufixo = sha1[:5], sha1[5:]
    futuro = _EXECUTOR.submit(_consultar_faixa, prefixo)
    try:
        resposta = futuro.result(timeout=TIMEOUT_S)
        for linha in resposta.splitlines():
            valor, _, contagem = linha.strip().partition(":")
            if valor == sufixo:
                return int(contagem or 0) > 0
        return False
    except Exception as e:  # noqa: BLE001 - qualquer falha do serviço, inclusive o prazo: aceita e registra
        futuro.cancel()
        motivo = "prazo esgotado" if isinstance(e, PrazoEsgotado) else type(e).__name__
        logger.warning("SEC-030: consulta de senhas vazadas indisponível (%s); senha aceita", motivo)
        return False


def exigir_senha_nao_vazada(senha: str | None, campo: str):
    """Resposta 422 se a senha nova aparece em vazamentos; None se não aparece (ou não foi enviada).

    Chamar na rota síncrona, depois da autorização e da conferência da senha atual."""
    if senha and senha_vazada(senha):
        return fail(MENSAGEM, erros={campo: MENSAGEM}, status_code=422)
    return None
