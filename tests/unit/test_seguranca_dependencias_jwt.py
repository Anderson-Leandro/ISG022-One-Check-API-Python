"""
Segurança — SEC-006: dependências com CVEs e sem lockfile

Cenário original: python-jose 3.3.0 (sem manutenção, CVEs de confusão de
algoritmo e DoS), cryptography 44.0.0 e python-dotenv 1.0.1 com CVEs, e nenhum
lockfile: as dependências transitivas ficavam fora dos scanners e podiam mudar
a cada build.

Regras verificadas:
  - os JWT são lidos pelo PyJWT, só com HS256 e com exp, sub e type obrigatórios
  - python-jose não é mais dependência
  - requirements.lock fixa todas as dependências (inclusive transitivas) com hash,
    nas mesmas versões do requirements.txt
"""
import base64
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest

from app.auth import create_access_token, decode_token
from app.config import JWT_ALGORITHM, JWT_SECRET

RAIZ = Path(__file__).resolve().parents[2]


def _exp(minutos: int = 5) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutos)


def _b64(dados: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(dados).encode()).rstrip(b"=").decode()


def _requisitos(arquivo: str) -> dict[str, str]:
    """{pacote normalizado: versão} das linhas `pacote==versão` do arquivo."""
    pinos = {}
    for linha in (RAIZ / arquivo).read_text().splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?==([^\s;\\]+)", linha.strip())
        if m:
            pinos[re.sub(r"[-_.]+", "-", m.group(1)).lower()] = m.group(3)
    return pinos


class TestTokens:
    def test_token_emitido_e_lido(self):
        payload = decode_token(create_access_token("u-1", "admin", 3))
        assert (payload["sub"], payload["role"], payload["type"], payload["ver"]) == ("u-1", "admin", "access", 3)

    def test_alg_none_recusado(self):
        token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64({'sub': 'u-1', 'type': 'access', 'role': 'admin'})}."
        assert decode_token(token) is None

    @pytest.mark.parametrize("alg", ["HS384", "HS512"])
    def test_outro_algoritmo_com_a_mesma_chave_recusado(self, alg):
        token = jwt.encode({"sub": "u-1", "type": "access", "exp": _exp()}, JWT_SECRET, algorithm=alg)
        assert decode_token(token) is None

    @pytest.mark.parametrize("ausente", ["exp", "sub", "type"])
    def test_claim_obrigatoria_ausente_recusada(self, ausente):
        claims = {"sub": "u-1", "type": "access", "role": "admin", "exp": _exp()}
        del claims[ausente]
        assert decode_token(jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)) is None

    def test_token_expirado_recusado(self):
        token = jwt.encode({"sub": "u-1", "type": "access", "exp": _exp(-1)}, JWT_SECRET, algorithm=JWT_ALGORITHM)
        assert decode_token(token) is None

    def test_assinatura_adulterada_recusada(self):
        cabecalho, _, assinatura = create_access_token("u-1", "locatario").split(".")
        forjado = f"{cabecalho}.{_b64({'sub': 'u-1', 'type': 'access', 'role': 'admin', 'exp': 9999999999})}.{assinatura}"
        assert decode_token(forjado) is None


class TestDependencias:
    def test_python_jose_removido(self):
        assert "python-jose" not in _requisitos("requirements.txt")
        assert "python-jose" not in _requisitos("requirements.lock")

    def test_lockfile_tem_hash_em_todos_os_pacotes(self):
        blocos = re.split(r"\n(?=[A-Za-z0-9])", (RAIZ / "requirements.lock").read_text())
        pacotes = [b for b in blocos if re.match(r"^[A-Za-z0-9_.\-]+(\[[^\]]*\])?==", b)]
        assert pacotes
        sem_hash = [b.split()[0] for b in pacotes if "--hash=sha256:" not in b]
        assert sem_hash == []

    def test_lockfile_coerente_com_requirements(self):
        diretas, travadas = _requisitos("requirements.txt"), _requisitos("requirements.lock")
        divergentes = {p: (v, travadas.get(p)) for p, v in diretas.items() if travadas.get(p) != v}
        assert divergentes == {}, "rode o comando do cabeçalho de requirements.lock"

    def test_lockfile_inclui_transitivas(self):
        travadas = _requisitos("requirements.lock")
        assert {"h11", "anyio", "pydantic", "click"} <= set(travadas)
