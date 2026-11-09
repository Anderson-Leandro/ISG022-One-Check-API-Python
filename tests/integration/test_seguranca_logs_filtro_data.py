"""
SEC-020 — Filtro de data inválido em GET /logs responde 422

Antes, uma data que não era ISO (ex.: de=31/10/2026) era ignorada em silêncio e a resposta trazia
os logs de todo o período, para quem tinha pedido um recorte. Agora:
- data inválida em `de` ou `ate` → 422 com a mensagem no campo, sem lista;
- `ate` só com a data vale o dia inteiro (até 23:59:59.999999);
- com fuso (ex.: -03:00), o instante é convertido para UTC, como o created_at;
- `de` depois de `ate` → 422.
"""

from datetime import datetime

import pytest

from app.models import LogOperacao
from tests.conftest import auth

LOGS = "/api/v1/logs"


@pytest.fixture
def logs_datados(db):
    for quando, acao in [
        (datetime(2026, 10, 30, 12, 0), "antes"),
        (datetime(2026, 10, 31, 0, 0), "inicio_do_dia"),
        (datetime(2026, 10, 31, 23, 59, 59, 900000), "fim_do_dia"),
        (datetime(2026, 11, 1, 0, 0), "dia_seguinte"),
    ]:
        db.add(LogOperacao(acao=acao, entidade="teste", created_at=quando))
    db.flush()


def _acoes(r):
    assert r.status_code == 200, r.text
    return {l["acao"] for l in r.json()["dados"]}


@pytest.mark.parametrize("campo", ["de", "ate"])
@pytest.mark.parametrize(
    "valor",
    [
        "31/10/2026",
        "2026-13-01",
        "ontem",
        "2026-10-31T25:00",
        "20261031",  # formato básico: o fromisoformat aceitaria, com o dia errado no fim do intervalo
        "2026-W44-6",  # data por semana
        "2026-10-31 10:00",  # sem o T
        "0001-01-01T00:00:00+05:00",
    ],
)
def test_data_invalida_responde_422_sem_lista(client, token_admin, logs_datados, campo, valor):
    r = client.get(LOGS, params={campo: valor}, headers=auth(token_admin))

    assert r.status_code == 422, r.text
    corpo = r.json()
    assert corpo["sucesso"] is False and not corpo.get("dados")
    assert campo in corpo["erros"]


def test_ate_so_com_a_data_vale_o_dia_inteiro(client, token_admin, logs_datados):
    r = client.get(
        LOGS, params={"entidade": "teste", "de": "2026-10-31", "ate": "2026-10-31"}, headers=auth(token_admin)
    )
    assert _acoes(r) == {"inicio_do_dia", "fim_do_dia"}


def test_data_e_hora_continuam_funcionando(client, token_admin, logs_datados):
    r = client.get(
        LOGS,
        params={"entidade": "teste", "de": "2026-10-30T12:00:00", "ate": "2026-10-31T00:00:00"},
        headers=auth(token_admin),
    )
    assert _acoes(r) == {"antes", "inicio_do_dia"}


def test_fuso_e_convertido_para_utc(client, token_admin, logs_datados):
    # 2026-10-31T21:00-03:00 é 2026-11-01T00:00 em UTC
    r = client.get(LOGS, params={"entidade": "teste", "de": "2026-10-31T21:00:00-03:00"}, headers=auth(token_admin))
    assert _acoes(r) == {"dia_seguinte"}


def test_de_depois_de_ate_responde_422(client, token_admin):
    r = client.get(LOGS, params={"de": "2026-11-02", "ate": "2026-11-01"}, headers=auth(token_admin))
    assert r.status_code == 422
    assert "ate" in r.json()["erros"]


def test_sem_filtro_de_data_continua_igual(client, token_admin, logs_datados):
    r = client.get(LOGS, params={"entidade": "teste"}, headers=auth(token_admin))
    assert _acoes(r) == {"antes", "inicio_do_dia", "fim_do_dia", "dia_seguinte"}


def test_gestor_continua_recebendo_403_antes_da_validacao(client, token_gestor):
    r = client.get(LOGS, params={"de": "31/10/2026"}, headers=auth(token_gestor))
    assert r.status_code == 403


def test_z_e_fracao_de_segundo_sao_aceitos(client, token_admin, logs_datados):
    r = client.get(
        LOGS,
        params={"entidade": "teste", "de": "2026-10-31T23:59:59.5Z", "ate": "2026-11-01T00:00Z"},
        headers=auth(token_admin),
    )
    assert _acoes(r) == {"fim_do_dia", "dia_seguinte"}


def test_mesmo_instante_em_de_e_ate_e_aceito(client, token_admin, logs_datados):
    r = client.get(
        LOGS,
        params={"entidade": "teste", "de": "2026-10-31T00:00", "ate": "2026-10-31T00:00"},
        headers=auth(token_admin),
    )
    assert _acoes(r) == {"inicio_do_dia"}


@pytest.mark.parametrize("valor", ["9999-12-31", "9999-12-31T23:59:59.999999"])
def test_ate_no_limite_do_calendario_e_422_e_nao_500(client, token_admin, valor):
    """O limite exclusivo do fim (dia seguinte, ou mais um microssegundo) passaria do ano 9999."""
    r = client.get(LOGS, params={"ate": valor}, headers=auth(token_admin))
    assert r.status_code == 422, r.text
    assert "ate" in r.json()["erros"]
