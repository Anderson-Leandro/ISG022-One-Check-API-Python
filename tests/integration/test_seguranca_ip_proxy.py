"""
Segurança — SEC-017: IP de origem lido do primeiro item do X-Forwarded-For, controlado pelo cliente

Cenário original: o uvicorn rodava com FORWARDED_ALLOW_IPS="*" e trocava o client pelo
primeiro item do X-Forwarded-For. O proxy do Render acrescenta o IP real ao cabeçalho que o
cliente enviou, em vez de sobrescrever (confirmado em produção em 2026-11-10: um login falho com
"X-Forwarded-For: 203.0.113.9" gravou esse IP no log_operacao). Mandando um IP inventado a cada
tentativa, o limite de falhas por IP nunca disparava e a trilha de auditoria gravava o IP forjado.

Regras verificadas:
  - com PROXY_SALTOS=N, o IP do cliente é o N-ésimo item a partir da direita, o que o proxy
    acrescentou; o que o cliente escreveu à esquerda não conta
  - sem PROXY_SALTOS (0, o padrão), o cabeçalho é ignorado e vale o IP da conexão
  - cabeçalho com menos itens que os saltos, ou item inválido, cai no IP da conexão
  - limite de tentativas e auditoria usam o mesmo IP
  - o uvicorn sobe sem ler os cabeçalhos de proxy, e o render.yaml não confia em todo IP
"""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from app import ip_cliente
from app.config import RATE_LIMIT_FALHAS_IP
from app.ip_cliente import ip_do_cliente
from app.models import LogOperacao
from tests.conftest import TEST_SENHA

RAIZ = Path(__file__).resolve().parents[2]
LOGIN = "/api/v1/auth/login"
PROXY = "198.51.100.7"  # o IP que o proxy acrescenta: o cliente real


@pytest.fixture
def atras_do_proxy(monkeypatch):
    """A API como no Render: um proxy na frente, que acrescenta o IP real ao X-Forwarded-For."""
    monkeypatch.setattr(ip_cliente, "PROXY_SALTOS", 1)


def _login_falho(client, email: str, xff: str | None):
    headers = {"X-Forwarded-For": xff} if xff is not None else {}
    return client.post(LOGIN, json={"email": email, "senha": "senha-errada"}, headers=headers)


def _ip_gravado(db) -> str | None:
    db.expire_all()
    log = db.query(LogOperacao).filter(LogOperacao.acao == "login_falho").one()
    return log.ip


class TestIpDoCliente:
    def test_sem_saltos_ignora_o_cabecalho(self):
        assert ip_do_cliente("203.0.113.9", "10.0.0.1", 0) == "10.0.0.1"

    def test_um_salto_usa_o_item_que_o_proxy_acrescentou(self):
        assert ip_do_cliente(f"203.0.113.9, {PROXY}", "10.0.0.1", 1) == PROXY

    def test_dois_saltos_usa_o_penultimo(self):
        assert ip_do_cliente(f"203.0.113.9, {PROXY}, 10.1.1.1", "10.0.0.1", 2) == PROXY

    def test_cabecalho_sem_o_item_do_proxy_cai_no_ip_da_conexao(self):
        assert ip_do_cliente(PROXY, "10.0.0.1", 2) == "10.0.0.1"

    @pytest.mark.parametrize("cabecalho", [None, "", " , ", "203.0.113.9, nao-e-ip", "203.0.113.9, 999.1.1.1"])
    def test_cabecalho_vazio_ou_invalido_cai_no_ip_da_conexao(self, cabecalho):
        assert ip_do_cliente(cabecalho, "10.0.0.1", 1) == "10.0.0.1"

    def test_ipv6_e_espacos(self):
        assert ip_do_cliente("203.0.113.9 ,  2001:db8::1 ", "10.0.0.1", 1) == "2001:db8::1"

    @pytest.mark.parametrize(
        "item, esperado",
        [(f"{PROXY}:5678", PROXY), ("[2001:db8::1]", "2001:db8::1"), ("[2001:db8::1]:443", "2001:db8::1")],
    )
    def test_item_com_porta_ou_colchetes(self, item, esperado):
        assert ip_do_cliente(f"203.0.113.9, {item}", "10.0.0.1", 1) == esperado


class TestEsquema:
    """--no-proxy-headers desliga também o X-Forwarded-Proto do uvicorn: o middleware o aplica."""

    def _location(self, client, headers):
        r = client.get("/api/v1/health/", headers=headers, follow_redirects=False)
        assert r.status_code == 307
        return r.headers["location"]

    def test_redirect_da_barra_final_continua_em_https(self, client, atras_do_proxy):
        assert self._location(client, {"X-Forwarded-Proto": "https"}).startswith("https://")

    def test_vale_o_ultimo_item_o_do_proxy(self, client, atras_do_proxy):
        assert self._location(client, {"X-Forwarded-Proto": "https, http"}).startswith("http://")

    @pytest.mark.parametrize("proto", ["javascript", "ftp", ""])
    def test_valor_desconhecido_e_ignorado(self, client, atras_do_proxy, proto):
        assert self._location(client, {"X-Forwarded-Proto": proto}).startswith("http://")

    def test_sem_proxy_configurado_o_cabecalho_e_ignorado(self, client):
        assert self._location(client, {"X-Forwarded-Proto": "https"}).startswith("http://")


class TestAuditoria:
    def test_ip_forjado_nao_vai_para_o_log(self, client, db, atras_do_proxy):
        _login_falho(client, "ninguem@test.com", f"203.0.113.9, {PROXY}")
        assert _ip_gravado(db) == PROXY

    def test_varias_linhas_do_cabecalho_contam_em_ordem(self, client, db, atras_do_proxy):
        # o proxy pode acrescentar uma linha nova em vez de concatenar na mesma
        client.post(
            LOGIN,
            json={"email": "ninguem@test.com", "senha": "x"},
            headers=[("X-Forwarded-For", "203.0.113.9"), ("X-Forwarded-For", PROXY)],
        )
        assert _ip_gravado(db) == PROXY

    def test_sem_proxy_configurado_o_cabecalho_e_ignorado(self, client, db):
        _login_falho(client, "ninguem@test.com", "203.0.113.9")
        assert _ip_gravado(db) == "testclient"


class TestLimitePorIp:
    def test_ip_forjado_a_cada_tentativa_nao_escapa_do_limite(self, client, user_locatario, atras_do_proxy):
        # cada e-mail falha uma vez só (abaixo do limite por conta): só o limite por IP pega
        for i in range(RATE_LIMIT_FALHAS_IP):
            assert _login_falho(client, f"alvo{i}@test.com", f"203.0.113.{i}, {PROXY}").status_code == 401
        r = client.post(
            LOGIN,
            json={"email": user_locatario.email, "senha": TEST_SENHA},
            headers={"X-Forwarded-For": f"203.0.113.250, {PROXY}"},
        )
        assert r.status_code == 429

    def test_outro_cliente_atras_do_mesmo_proxy_nao_e_bloqueado(self, client, user_locatario, atras_do_proxy):
        for i in range(RATE_LIMIT_FALHAS_IP):
            _login_falho(client, f"alvo{i}@test.com", PROXY)
        r = client.post(
            LOGIN,
            json={"email": user_locatario.email, "senha": TEST_SENHA},
            headers={"X-Forwarded-For": "198.51.100.8"},
        )
        assert r.status_code == 200


class TestImplantacao:
    def test_render_nao_confia_em_todo_ip(self):
        envs = {e["key"]: e for e in yaml.safe_load((RAIZ / "render.yaml").read_text())["services"][0]["envVars"]}
        assert envs.get("FORWARDED_ALLOW_IPS", {}).get("value") != "*"
        assert envs["PROXY_SALTOS"]["value"] == "1"

    def test_uvicorn_sobe_sem_ler_cabecalhos_de_proxy(self, tmp_path):
        # mesmo com FORWARDED_ALLOW_IPS="*" ainda no painel, o uvicorn não troca o client
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        log = tmp_path / "chamadas.log"
        for nome in ("python", "uvicorn"):
            stub = bin_dir / nome
            stub.write_text(f'#!/usr/bin/env bash\necho "{nome} $*" >> "{log}"\n')
            stub.chmod(0o755)
        env = {"PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": os.environ.get("HOME", "/tmp")}
        r = subprocess.run(["bash", "start.sh"], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, r.stderr
        uvicorn = next(linha for linha in log.read_text().splitlines() if linha.startswith("uvicorn"))
        assert "--no-proxy-headers" in uvicorn.split()
