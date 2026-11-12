"""
Segurança — SEC-030: recusar senhas que aparecem em vazamentos conhecidos

Cenário original: a política de senha (SEC-011) recusava as curtas, as só numéricas e uma lista de palavras
comuns, mas aceitava senhas fortes no formato que já circulam em vazamentos, usadas em credential stuffing.

Regras verificadas (decisão do PO em 2026-11-11):
  - senha nova presente na base do Have I Been Pwned → 422, com a mensagem em erros.<campo>
  - k-anonymity: só os 5 primeiros caracteres do SHA-1 saem da API; o restante é comparado localmente
  - prazo total de 2 s; serviço lento, fora do ar ou com resposta estranha → a senha é aceita e o fato vai
    para o log, sem a senha nem o hash (fail open)
  - a consulta acontece na rota, depois da conferência da senha atual: senha atual errada → 403, sem consulta
  - as linhas de preenchimento (contagem 0) do Add-Padding não contam como vazamento
  - SENHA_VAZADA_CONSULTA=false desliga a consulta (nos testes, a conftest desliga; aqui ela é ligada)
"""

import hashlib
import importlib
import logging
import time

import pytest

from app import senhas_vazadas
from tests.conftest import TEST_SENHA, auth

API = "/api/v1/usuarios"
VAZADA = "Correto.Cavalo#Bateria9"
LIMPA = "Outra.Frase#Segura42"


def _sha1(senha: str) -> str:
    return hashlib.sha1(senha.encode(), usedforsecurity=False).hexdigest().upper()  # o formato do serviço


@pytest.fixture
def servico(monkeypatch):
    """Liga a consulta e troca a chamada HTTP por uma resposta controlada; guarda os prefixos pedidos."""
    pedidos: list[str] = []
    resposta = {"texto": ""}

    def consultar(prefixo: str) -> str:
        pedidos.append(prefixo)
        if isinstance(resposta["texto"], Exception):
            raise resposta["texto"]
        return resposta["texto"]

    monkeypatch.setattr(senhas_vazadas, "CONSULTA_ATIVA", True)
    monkeypatch.setattr(senhas_vazadas, "_consultar_faixa", consultar)
    resposta["texto"] = f"{_sha1(VAZADA)[5:]}:1234\r\n0123456789ABCDEF0123456789ABCDEF012:0\r\n"
    return pedidos, resposta


def _trocar(client, token, nova):
    return client.put(f"{API}/me/senha", json={"senha_atual": TEST_SENHA, "nova_senha": nova}, headers=auth(token))


class TestRecusa:
    def test_senha_vazada_recebe_422_com_a_mensagem_do_campo(self, client, token_locatario, servico):
        r = _trocar(client, token_locatario, VAZADA)
        assert r.status_code == 422
        assert "vazamentos" in r.json()["erros"]["nova_senha"]

    def test_senha_que_nao_aparece_e_aceita(self, client, token_locatario, servico):
        assert _trocar(client, token_locatario, LIMPA).status_code == 200

    def test_criacao_de_usuario_tambem_confere(self, client, token_admin, servico):
        corpo = {"nome": "Nova", "email": "nova@test.com", "senha": VAZADA, "role": "locatario"}
        r = client.post(API, json=corpo, headers=auth(token_admin))
        assert r.status_code == 422 and "senha" in r.json()["erros"]

    def test_preenchimento_com_contagem_zero_nao_conta(self, servico):
        pedidos, resposta = servico
        resposta["texto"] = f"{_sha1(LIMPA)[5:]}:0\r\n"
        assert senhas_vazadas.senha_vazada(LIMPA) is False


class TestKAnonymity:
    def test_so_o_prefixo_de_5_caracteres_sai_da_api(self, client, token_locatario, servico):
        pedidos, _ = servico
        _trocar(client, token_locatario, LIMPA)
        assert pedidos == [_sha1(LIMPA)[:5]]

    def test_a_requisicao_real_usa_so_o_prefixo_e_o_padding(self, monkeypatch):
        capturado = {}

        class _Resposta:
            status = 200
            headers = {"Content-Type": "text/plain"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, _limite=None):
                return b""

        def urlopen(req, timeout):
            capturado.update(url=req.full_url, headers=dict(req.header_items()), timeout=timeout)
            return _Resposta()

        monkeypatch.setattr(senhas_vazadas.urllib.request, "urlopen", urlopen)
        senhas_vazadas._consultar_faixa("ABCDE")
        assert capturado["url"] == "https://api.pwnedpasswords.com/range/ABCDE"
        assert capturado["headers"].get("Add-padding") == "true"
        assert capturado["timeout"] <= 2

    def test_prefixo_fora_do_formato_nao_chega_a_rede(self, monkeypatch):
        monkeypatch.setattr(senhas_vazadas.urllib.request, "urlopen", lambda *a, **k: pytest.fail("chamou a rede"))
        with pytest.raises(ValueError):
            senhas_vazadas._consultar_faixa("../x")


class TestOrdemNaRota:
    def test_senha_atual_errada_recebe_403_sem_consultar(self, client, token_locatario, servico):
        pedidos, _ = servico
        r = client.put(
            f"{API}/me/senha", json={"senha_atual": "errada", "nova_senha": VAZADA}, headers=auth(token_locatario)
        )
        assert r.status_code == 403
        assert pedidos == []

    def test_patch_do_proprio_perfil_tambem_confere(self, client, token_locatario, servico):
        r = client.patch(
            f"{API}/me", json={"senha_atual": TEST_SENHA, "senha_nova": VAZADA}, headers=auth(token_locatario)
        )
        assert r.status_code == 422 and "senha_nova" in r.json()["erros"]


class TestFailOpen:
    @pytest.mark.parametrize("falha", [TimeoutError("demorou"), OSError("sem rede"), ValueError("estranha")])
    def test_servico_fora_do_ar_aceita_e_registra_sem_a_senha(self, client, token_locatario, servico, caplog, falha):
        _, resposta = servico
        resposta["texto"] = falha
        with caplog.at_level(logging.WARNING):
            assert _trocar(client, token_locatario, VAZADA).status_code == 200
        assert "SEC-030" in caplog.text
        assert VAZADA not in caplog.text and _sha1(VAZADA) not in caplog.text

    def test_servico_lento_aceita_dentro_do_prazo(self, monkeypatch, caplog):
        monkeypatch.setattr(senhas_vazadas, "CONSULTA_ATIVA", True)
        monkeypatch.setattr(senhas_vazadas, "TIMEOUT_S", 0.2)
        monkeypatch.setattr(senhas_vazadas, "_consultar_faixa", lambda p: time.sleep(1) or "")
        inicio = time.monotonic()
        with caplog.at_level(logging.WARNING):
            assert senhas_vazadas.senha_vazada(VAZADA) is False
        assert time.monotonic() - inicio < 0.8
        assert "prazo esgotado" in caplog.text

    def test_resposta_que_nao_e_texto_e_recusada(self, monkeypatch):
        class _Html:
            status = 200
            headers = {"Content-Type": "text/html"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, _limite=None):
                return b"<html>portal</html>"

        monkeypatch.setattr(senhas_vazadas.urllib.request, "urlopen", lambda req, timeout: _Html())
        with pytest.raises(ValueError, match="inesperada"):
            senhas_vazadas._consultar_faixa("ABCDE")

    def test_resposta_grande_demais_e_recusada(self, monkeypatch):
        class _Enorme:
            status = 200
            headers = {"Content-Type": "text/plain"}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, limite=None):
                return b"x" * limite

        monkeypatch.setattr(senhas_vazadas.urllib.request, "urlopen", lambda req, timeout: _Enorme())
        with pytest.raises(ValueError, match="grande"):
            senhas_vazadas._consultar_faixa("ABCDE")

    def test_desligada_nao_consulta(self, monkeypatch):
        chamadas = []
        monkeypatch.setattr(senhas_vazadas, "CONSULTA_ATIVA", False)
        monkeypatch.setattr(senhas_vazadas, "_consultar_faixa", lambda p: chamadas.append(p) or "")
        assert senhas_vazadas.senha_vazada(VAZADA) is False
        assert chamadas == []


class TestVariavel:
    @pytest.mark.parametrize(
        "valor,esperado", [("", True), ("true", True), ("off", False), ("false", False), ("0", False)]
    )
    def test_valores_da_variavel(self, monkeypatch, valor, esperado):
        from app import config

        monkeypatch.setenv("SENHA_VAZADA_CONSULTA", valor)
        try:
            assert importlib.reload(config).SENHA_VAZADA_CONSULTA is esperado
        finally:
            monkeypatch.setenv("SENHA_VAZADA_CONSULTA", "false")
            importlib.reload(config)
