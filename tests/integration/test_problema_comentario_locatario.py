"""
US-019 — O locatário comenta no próprio problema enquanto não estiver resolvido (ADR-0012, item 7)

POST /problemas/{id}/atualizacoes passa a aceitar o locatário dono do contrato do problema, enquanto o
problema não estiver resolvido. Admin e gestor continuam como antes; vistoriador e locatário de outro
contrato recebem 403. Mudar o status continua só com admin e gestor.
"""
from datetime import date

import pytest

from app.models import AtualizacaoProblema, Contrato, Imovel, Problema
from tests.conftest import auth, foto_do_banco

API = "/api/v1"
TEXTO = "A infiltração voltou depois da chuva."


@pytest.fixture
def problema(db, contrato):
    pb = Problema(contrato_id=contrato.id, titulo="Infiltração no quarto")
    db.add(pb)
    db.flush()
    return pb


@pytest.fixture
def problema_alheio(db, user_locatario_2):
    im = Imovel(tipo="casa", status="locado", garagem=False, garagem_vagas=0)
    db.add(im)
    db.flush()
    ct = Contrato(imovel_id=im.id, locatario_id=user_locatario_2.id, data_inicio=date(2025, 1, 1),
                  data_fim=date(2025, 12, 31), status="ativo")
    db.add(ct)
    db.flush()
    pb = Problema(contrato_id=ct.id, titulo="Problema de outro contrato")
    db.add(pb)
    db.flush()
    return pb


def _comentar(client, problema_id, token, texto=TEXTO):
    return client.post(f"{API}/problemas/{problema_id}/atualizacoes", json={"descricao": texto}, headers=auth(token))


def _atualizacoes(db, problema_id):
    db.expire_all()
    return db.query(AtualizacaoProblema).filter(AtualizacaoProblema.problema_id == problema_id).all()


@pytest.mark.parametrize("status", ["aberto", "em_andamento"])
def test_locatario_dono_comenta_no_problema_nao_resolvido(client, db, problema, user_locatario, token_locatario, status):
    problema.status = status
    db.flush()

    r = _comentar(client, problema.id, token_locatario)

    assert r.status_code == 201, r.text
    assert r.json()["dados"]["descricao"] == TEXTO
    [a] = _atualizacoes(db, problema.id)
    assert (a.autor_id, a.descricao) == (user_locatario.id, TEXTO)


@pytest.mark.parametrize("status", ["resolvido", "fechado"])
def test_problema_encerrado_responde_409(client, db, problema, token_locatario, status):
    problema.status = status
    db.flush()
    antes = foto_do_banco(db)

    r = _comentar(client, problema.id, token_locatario)

    assert r.status_code == 409, r.text
    assert r.json()["erro"] == "Não é possível comentar num problema resolvido"
    assert foto_do_banco(db) == antes


def test_gestor_continua_comentando_no_problema_resolvido(client, db, problema, token_gestor):
    problema.status = "resolvido"
    db.flush()
    assert _comentar(client, problema.id, token_gestor).status_code == 201


def test_locatario_de_outro_contrato_recebe_403(client, db, problema_alheio, token_locatario):
    antes = foto_do_banco(db)

    r = _comentar(client, problema_alheio.id, token_locatario)

    assert r.status_code == 403, r.text
    assert r.json()["erro"] == "Você não tem acesso aos problemas deste contrato"
    assert foto_do_banco(db) == antes


def test_vistoriador_recebe_403_mesmo_para_id_inexistente(client, db, problema, token_vistoriador):
    """O perfil é barrado antes da busca: o vistoriador não distingue um ID que existe de um que não existe."""
    antes = foto_do_banco(db)
    existente = _comentar(client, problema.id, token_vistoriador)
    inexistente = _comentar(client, "00000000-0000-0000-0000-000000000000", token_vistoriador)
    assert (existente.status_code, inexistente.status_code) == (403, 403)
    assert foto_do_banco(db) == antes


def test_negado_com_upload_nao_grava_arquivo(client, db, problema_alheio, token_locatario):
    from app.config import UPLOAD_DIR
    from tests.conftest import small_image_bytes
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    arquivos_antes = sorted(p.name for p in UPLOAD_DIR.iterdir())

    r = client.post(f"{API}/problemas/{problema_alheio.id}/atualizacoes", headers=auth(token_locatario),
                    data={"descricao": TEXTO}, files={"foto": ("a.png", small_image_bytes(), "image/png")})

    assert r.status_code == 403, r.text
    assert sorted(p.name for p in UPLOAD_DIR.iterdir()) == arquivos_antes


def test_locatario_continua_sem_mudar_o_status(client, db, problema, token_locatario):
    antes = foto_do_banco(db)
    r = client.patch(f"{API}/problemas/{problema.id}/status", json={"status": "resolvido"}, headers=auth(token_locatario))
    assert r.status_code == 403
    assert foto_do_banco(db) == antes


def test_comentario_do_locatario_avisa_a_equipe_e_nao_ele_mesmo(client, problema, user_locatario, token_locatario, monkeypatch):
    from app.routers import problemas as rota
    avisos = {"usuario": [], "admins": []}
    monkeypatch.setattr(rota, "notificar_usuario", lambda db, uid, *a: avisos["usuario"].append(uid))
    monkeypatch.setattr(rota, "notificar_admins", lambda db, *a: avisos["admins"].append(True))

    assert _comentar(client, problema.id, token_locatario).status_code == 201

    assert avisos == {"usuario": [], "admins": [True]}


def test_comentario_da_equipe_continua_avisando_o_locatario(client, problema, user_locatario, token_gestor, monkeypatch):
    from app.routers import problemas as rota
    avisos = []
    monkeypatch.setattr(rota, "notificar_usuario", lambda db, uid, *a: avisos.append(uid))
    assert _comentar(client, problema.id, token_gestor).status_code == 201
    assert avisos == [user_locatario.id]
