"""
US-017 — Histórico do imóvel: GET /api/v1/imoveis/{id}/historico

Contratos, vistorias e problemas do imóvel em ordem cronológica (pela data de registro). Cada perfil vê
só o que já acessa pelas listagens:
  - admin e gestor: tudo;
  - locatário: só os próprios contratos, as vistorias e os problemas deles;
  - vistoriador: só os contratos em que tem vistoria e só as vistorias dele; nenhum problema.
O acesso ao imóvel segue a mesma regra de GET /imoveis/{id}.
"""

from datetime import date, datetime

import pytest

from app.models import Checklist, Contrato, Problema, Usuario
from tests.conftest import _SENHA_HASH, auth

API = "/api/v1"


def _em(dia: int) -> datetime:
    return datetime(2026, 1, dia, 9, 0, 0)


@pytest.fixture
def outro_locatario(db):
    u = Usuario(nome="Locatário Antigo", email="antigo@test.com", senha_hash=_SENHA_HASH, role="locatario", ativo=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def outro_vistoriador(db):
    u = Usuario(
        nome="Outro Vistoriador",
        email="outro.vist.hist@test.com",
        senha_hash=_SENHA_HASH,
        role="vistoriador",
        mfa_enabled=True,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def historico(db, imovel, contrato, user_vistoriador, outro_locatario, outro_vistoriador):
    """Linha do tempo do imóvel:
    dia 1  contrato antigo (outro locatário, encerrado)
    dia 2  vistoria do contrato antigo (outro vistoriador)
    dia 3  problema do contrato antigo
    dia 5  contrato atual (fixture `contrato`, do user_locatario)
    dia 6  vistoria do contrato atual (user_vistoriador)
    dia 7  problema do contrato atual
    """
    antigo = Contrato(
        imovel_id=imovel.id,
        locatario_id=outro_locatario.id,
        data_inicio=date(2024, 1, 1),
        data_fim=date(2024, 12, 31),
        status="encerrado",
        created_at=_em(1),
    )
    db.add(antigo)
    db.flush()
    contrato.created_at = _em(5)
    v_antiga = Checklist(
        contrato_id=antigo.id, vistoriador_id=outro_vistoriador.id, tipo="inicial", status="aceito", created_at=_em(2)
    )
    v_atual = Checklist(
        contrato_id=contrato.id,
        vistoriador_id=user_vistoriador.id,
        tipo="inicial",
        status="em_preenchimento",
        created_at=_em(6),
    )
    p_antigo = Problema(contrato_id=antigo.id, titulo="Vazamento antigo", created_at=_em(3))
    p_atual = Problema(contrato_id=contrato.id, titulo="Tomada solta", created_at=_em(7))
    db.add_all([v_antiga, v_atual, p_antigo, p_atual])
    db.flush()
    return {
        "contrato_antigo": antigo.id,
        "vistoria_antiga": v_antiga.id,
        "problema_antigo": p_antigo.id,
        "contrato_atual": contrato.id,
        "vistoria_atual": v_atual.id,
        "problema_atual": p_atual.id,
    }


def _eventos(client, imovel_id, token):
    r = client.get(f"{API}/imoveis/{imovel_id}/historico", headers=auth(token))
    assert r.status_code == 200, r.text
    return [(e["tipo"], e["dados"]["id"]) for e in r.json()["dados"]["eventos"]]


def test_gestor_ve_tudo_em_ordem_cronologica(client, imovel, historico, token_gestor):
    h = historico
    assert _eventos(client, imovel.id, token_gestor) == [
        ("contrato", h["contrato_antigo"]),
        ("vistoria", h["vistoria_antiga"]),
        ("problema", h["problema_antigo"]),
        ("contrato", h["contrato_atual"]),
        ("vistoria", h["vistoria_atual"]),
        ("problema", h["problema_atual"]),
    ]


def test_evento_traz_a_data_e_o_registro(client, imovel, historico, token_admin):
    r = client.get(f"{API}/imoveis/{imovel.id}/historico", headers=auth(token_admin))
    primeiro = r.json()["dados"]["eventos"][0]
    assert r.json()["dados"]["imovel_id"] == imovel.id
    assert primeiro["data"] == _em(1).isoformat()
    assert primeiro["dados"]["status"] == "encerrado"


def test_locatario_ve_so_o_proprio_contrato(client, imovel, historico, token_locatario):
    h = historico
    assert _eventos(client, imovel.id, token_locatario) == [
        ("contrato", h["contrato_atual"]),
        ("vistoria", h["vistoria_atual"]),
        ("problema", h["problema_atual"]),
    ]


def test_vistoriador_ve_so_o_que_vistoriou(client, imovel, historico, token_vistoriador):
    h = historico
    assert _eventos(client, imovel.id, token_vistoriador) == [
        ("contrato", h["contrato_atual"]),
        ("vistoria", h["vistoria_atual"]),
    ]


def test_ex_locatario_ve_so_o_contrato_antigo_dele(client, imovel, historico, outro_locatario):
    """Como em GET /contratos: o contrato encerrado continua visível para quem o teve."""
    from app.auth import create_access_token

    h = historico
    token = create_access_token(outro_locatario.id, outro_locatario.role)
    assert _eventos(client, imovel.id, token) == [
        ("contrato", h["contrato_antigo"]),
        ("vistoria", h["vistoria_antiga"]),
        ("problema", h["problema_antigo"]),
    ]


def test_locatario_com_contrato_antigo_e_atual_ve_os_dois(
    client, db, imovel, contrato, historico, user_locatario, token_locatario
):
    db.get(Contrato, historico["contrato_antigo"]).locatario_id = user_locatario.id
    db.flush()
    assert [t for t, _ in _eventos(client, imovel.id, token_locatario)] == [
        "contrato",
        "vistoria",
        "problema",
        "contrato",
        "vistoria",
        "problema",
    ]


def test_locatario_sem_contrato_no_imovel_recebe_403(client, db, imovel, historico):
    from app.auth import create_access_token

    estranho = Usuario(
        nome="Sem Contrato", email="sem.contrato@test.com", senha_hash=_SENHA_HASH, role="locatario", ativo=True
    )
    db.add(estranho)
    db.flush()
    r = client.get(
        f"{API}/imoveis/{imovel.id}/historico", headers=auth(create_access_token(estranho.id, estranho.role))
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "Você não tem acesso a este imóvel"


def test_eventos_com_a_mesma_data_tem_ordem_estavel(client, db, imovel, contrato, historico, token_admin):
    # Gravados em ordem inversa à dos IDs: sem o desempate pelo ID, a ordem viria a da gravação
    mesmos = [
        Problema(
            id=f"{c * 8}-0000-0000-0000-000000000000"[:36],
            contrato_id=contrato.id,
            titulo=f"Mesmo instante {c}",
            created_at=_em(9),
        )
        for c in "fca"
    ]
    db.add_all(mesmos)
    db.flush()
    ultimos = [i for t, i in _eventos(client, imovel.id, token_admin)][-3:]
    assert ultimos == sorted(p.id for p in mesmos)


def test_vistoriador_sem_vistoria_no_imovel_recebe_403(client, imovel, contrato, token_vistoriador):
    r = client.get(f"{API}/imoveis/{imovel.id}/historico", headers=auth(token_vistoriador))
    assert r.status_code == 403, r.text


def test_registro_excluido_nao_aparece(client, db, imovel, historico, user_admin, token_admin):
    from app.exclusao import marcar_excluido

    marcar_excluido(db.get(Problema, historico["problema_atual"]), user_admin)
    db.flush()
    ids = [i for _, i in _eventos(client, imovel.id, token_admin)]
    assert historico["problema_atual"] not in ids
    assert len(ids) == 5


def test_imovel_inexistente_responde_404(client, token_admin):
    r = client.get(f"{API}/imoveis/00000000-0000-0000-0000-000000000000/historico", headers=auth(token_admin))
    assert r.status_code == 404
    assert r.json()["erro"] == "Imóvel não encontrado"


def test_sem_token_responde_401(client, imovel):
    assert client.get(f"{API}/imoveis/{imovel.id}/historico").status_code == 401


def test_vistoriador_nao_ve_vistoria_de_outro_no_mesmo_contrato(
    client, db, imovel, contrato, historico, outro_vistoriador, token_vistoriador
):
    alheia = Checklist(
        contrato_id=contrato.id,
        vistoriador_id=outro_vistoriador.id,
        tipo="encerramento",
        status="em_preenchimento",
        created_at=_em(8),
    )
    db.add(alheia)
    db.flush()
    ids = [i for _, i in _eventos(client, imovel.id, token_vistoriador)]
    assert alheia.id not in ids
    assert ids == [historico["contrato_atual"], historico["vistoria_atual"]]
