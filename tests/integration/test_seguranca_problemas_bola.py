"""
Segurança — Item 6: BOLA no acesso a problemas por ID

Cenário original: GET /contratos/{id}/problemas negava vistoriador e
visualizador, mas GET /problemas/{id} e GET /problemas/{id}/atualizacoes só
restringiam o locatário. Qualquer vistoriador ou visualizador lia qualquer
problema (e suas atualizações) de qualquer contrato, bastando o ID.

Regra verificada: a mesma da listagem, em todas as rotas de leitura —
admin, gestor e o locatário dono do contrato.
"""
import pytest

from app.models import AtualizacaoProblema, Problema
from tests.conftest import auth

BASE_CONTRATOS = "/api/v1/contratos"
BASE_PROBLEMAS = "/api/v1/problemas"


@pytest.fixture
def problema(db, contrato, user_admin):
    pb = Problema(contrato_id=contrato.id, titulo="Infiltração", descricao="Mancha no teto da sala")
    db.add(pb)
    db.flush()
    db.add(AtualizacaoProblema(problema_id=pb.id, autor_id=user_admin.id, descricao="Técnico agendado"))
    db.flush()
    return pb


def _rotas(contrato_id, problema_id):
    return {
        "lista": f"{BASE_CONTRATOS}/{contrato_id}/problemas",
        "por_id": f"{BASE_PROBLEMAS}/{problema_id}",
        "atualizacoes": f"{BASE_PROBLEMAS}/{problema_id}/atualizacoes",
    }


class TestPerfisSemVinculo:
    @pytest.mark.parametrize("token_fixture", ["token_vistoriador", "token_visualizador"])
    @pytest.mark.parametrize("rota", ["por_id", "atualizacoes"])
    def test_sem_vinculo_recebe_403(self, client, request, contrato, problema, token_fixture, rota):
        token = request.getfixturevalue(token_fixture)
        r = client.get(_rotas(contrato.id, problema.id)[rota], headers=auth(token))
        assert r.status_code == 403
        assert r.json()["sucesso"] is False
        assert "Infiltração" not in r.text


class TestConsistenciaListaPorId:
    @pytest.mark.parametrize(
        "token_fixture",
        ["token_admin", "token_gestor", "token_locatario", "token_vistoriador", "token_visualizador"],
    )
    def test_mesma_decisao_em_todas_as_rotas(self, client, request, contrato, problema, token_fixture):
        token = request.getfixturevalue(token_fixture)
        status = {
            nome: client.get(url, headers=auth(token)).status_code
            for nome, url in _rotas(contrato.id, problema.id).items()
        }
        assert len(set(status.values())) == 1, status


class TestCaminhosLegitimos:
    @pytest.mark.parametrize("token_fixture", ["token_admin", "token_gestor", "token_locatario"])
    def test_acesso_permitido(self, client, request, contrato, problema, token_fixture):
        token = request.getfixturevalue(token_fixture)
        rotas = _rotas(contrato.id, problema.id)
        r = client.get(rotas["por_id"], headers=auth(token))
        assert r.status_code == 200
        assert r.json()["dados"]["id"] == problema.id
        r = client.get(rotas["atualizacoes"], headers=auth(token))
        assert r.status_code == 200
        assert len(r.json()["dados"]) == 1
