"""Limite de tentativas falhas de autenticação (login, MFA e reautenticação).

O estado fica na memória do processo: vale para uma instância com um worker
(o deploy atual). Com várias instâncias ou workers, cada um conta à parte e o
limite efetivo se multiplica; nesse caso, mover o contador para Redis ou banco.
"""
import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from app.config import RATE_LIMIT_FALHAS_CONTA, RATE_LIMIT_FALHAS_IP, RATE_LIMIT_JANELA_MIN

_MAX_CHAVES = 10_000


class LimitadorTentativas:
    def __init__(self, janela_s: float):
        self.janela_s = janela_s
        self._falhas: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._agora = time.monotonic

    def _recentes(self, chave: str) -> deque[float] | None:
        fila = self._falhas.get(chave)
        if fila is None:
            return None
        limite = self._agora() - self.janela_s
        while fila and fila[0] <= limite:
            fila.popleft()
        if not fila:
            del self._falhas[chave]
            return None
        return fila

    def espera(self, chave: str, maximo: int) -> int:
        """Segundos até a chave voltar a aceitar tentativas (0 = liberada)."""
        with self._lock:
            fila = self._recentes(chave)
            if not fila or len(fila) < maximo:
                return 0
            return max(1, math.ceil(fila[-maximo] + self.janela_s - self._agora()))

    def falha(self, chave: str) -> None:
        with self._lock:
            if len(self._falhas) >= _MAX_CHAVES:
                # Muitos e-mails diferentes (varredura): descarta as chaves já expiradas
                for k in list(self._falhas):
                    self._recentes(k)
            self._falhas.setdefault(chave, deque(maxlen=1000)).append(self._agora())

    def limpar(self, chave: str) -> None:
        with self._lock:
            self._falhas.pop(chave, None)

    def reset(self) -> None:
        with self._lock:
            self._falhas.clear()


limitador = LimitadorTentativas(RATE_LIMIT_JANELA_MIN * 60)


class Tentativas:
    """Tentativas de um escopo (login, mfa, reauth) para uma conta, somadas às do IP de origem.

    Uso: verificar() antes de conferir a credencial, falhou() quando ela não confere,
    sucesso() quando confere (zera só a conta; o IP continua contando).
    """

    def __init__(self, request: Request, escopo: str, conta: str):
        ip = request.client.host if request.client else "desconhecido"
        self._conta = (f"{escopo}:{conta}", RATE_LIMIT_FALHAS_CONTA)
        self._ip = (f"ip:{ip}", RATE_LIMIT_FALHAS_IP)

    def verificar(self) -> None:
        espera = max(limitador.espera(chave, maximo) for chave, maximo in (self._conta, self._ip))
        if espera:
            raise HTTPException(
                status_code=429,
                detail="Muitas tentativas. Tente novamente mais tarde.",
                headers={"Retry-After": str(espera)},
            )

    def falhou(self) -> None:
        limitador.falha(self._conta[0])
        limitador.falha(self._ip[0])

    def sucesso(self) -> None:
        limitador.limpar(self._conta[0])
