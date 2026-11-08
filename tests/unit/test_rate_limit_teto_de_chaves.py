"""
Segurança — SEC-034: teto de chaves do limitador de tentativas (app/rate_limit.py)

Uma varredura com muitos e-mails diferentes cria uma chave por e-mail. Acima de _MAX_CHAVES, o
limitador descarta as chaves já expiradas antes de registrar a falha nova, para a memória não crescer
sem limite (OWASP API4:2023). A avaliação SPK-005 mostrou que esse ramo nunca era executado.

O relógio é controlado: _agora devolve o valor que o teste define.
"""
import pytest

from app import rate_limit
from app.rate_limit import LimitadorTentativas

JANELA_S = 60


@pytest.fixture
def relogio():
    return {"t": 1000.0}


@pytest.fixture
def limitador(relogio):
    lim = LimitadorTentativas(JANELA_S)
    lim._agora = lambda: relogio["t"]
    return lim


def _encher(limitador, quantidade, prefixo="email"):
    for i in range(quantidade):
        limitador.falha(f"login:{prefixo}{i}")


def test_acima_do_teto_descarta_expiradas_e_conta_a_nova(limitador, relogio):
    _encher(limitador, rate_limit._MAX_CHAVES)
    assert len(limitador._falhas) == rate_limit._MAX_CHAVES

    relogio["t"] += JANELA_S + 1  # todas as anteriores expiraram
    limitador.falha("login:nova")

    assert list(limitador._falhas) == ["login:nova"]
    assert limitador.espera("login:nova", maximo=1) > 0


def test_acima_do_teto_mantem_as_que_ainda_valem(limitador, relogio):
    _encher(limitador, rate_limit._MAX_CHAVES - 1, prefixo="antiga")
    relogio["t"] += JANELA_S + 1
    limitador.falha("login:recente")  # dentro da janela atual: o teto é atingido com ela

    limitador.falha("login:nova")

    assert sorted(limitador._falhas) == ["login:nova", "login:recente"]
    assert limitador.espera("login:recente", maximo=1) > 0


def test_abaixo_do_teto_nao_descarta(limitador, relogio):
    _encher(limitador, 10)
    relogio["t"] += JANELA_S + 1

    limitador.falha("login:nova")

    # Abaixo do teto, as expiradas só saem quando a própria chave é consultada
    assert len(limitador._falhas) == 11
