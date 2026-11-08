"""
Segurança — DEBT-017: as regras de acesso negam por padrão os perfis que não citam (CWE-636)

As regras restringiam só locatário e vistoriador; qualquer outro perfil caía no acesso total. Hoje
get_current_user, o login e o refresh recusam perfis fora de ROLES (ADR-0009), mas um caminho que carregue
o usuário sem passar por eles (job, dependência nova) trataria um perfil desconhecido como admin. Estes
testes contornam o get_current_user de propósito e conferem que cada regra nega o perfil desconhecido.
"""
import pytest
from fastapi import HTTPException

from app import deps
from app.main import app
from app.models import Checklist, Usuario
from app.routers import dashboard
from tests.conftest import _SENHA_HASH, auth

API = "/api/v1"


@pytest.fixture
def perfil_desconhecido(db):
    u = Usuario(nome="Perfil Fora da Lista", email="fora.da.lista@test.com", senha_hash=_SENHA_HASH,
                role="auditor", ativo=True)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def sem_o_portao(perfil_desconhecido):
    """Simula um caminho que não passa pelo get_current_user: a dependência devolve o usuário direto."""
    app.dependency_overrides[deps.get_current_user] = lambda: perfil_desconhecido
    yield
    app.dependency_overrides.pop(deps.get_current_user, None)


class TestRegrasChamadasDiretamente:
    def test_acesso_ao_contrato(self, db, contrato, perfil_desconhecido):
        with pytest.raises(HTTPException) as e:
            deps.assert_acesso_contrato(db, contrato, perfil_desconhecido)
        assert e.value.status_code == 403

    def test_acesso_ao_imovel(self, db, imovel, perfil_desconhecido):
        with pytest.raises(HTTPException) as e:
            deps.assert_acesso_imovel(db, imovel.id, perfil_desconhecido)
        assert e.value.status_code == 403

    def test_acesso_aos_problemas(self, contrato, perfil_desconhecido):
        with pytest.raises(HTTPException) as e:
            deps.assert_acesso_problemas(contrato, perfil_desconhecido)
        assert e.value.status_code == 403

    def test_recorte_do_dashboard(self, db, perfil_desconhecido):
        with pytest.raises(HTTPException) as e:
            dashboard._contratos_visiveis(db, perfil_desconhecido)
        assert e.value.status_code == 403

    @pytest.mark.parametrize("perfil", ["admin", "gestor"])
    def test_admin_e_gestor_continuam_liberados(self, db, contrato, imovel, user_admin, user_gestor, perfil):
        u = user_admin if perfil == "admin" else user_gestor
        deps.assert_acesso_contrato(db, contrato, u)
        deps.assert_acesso_imovel(db, imovel.id, u)
        assert dashboard._contratos_visiveis(db, u) is None


@pytest.mark.parametrize("rota", [
    "/contratos", "/contratos/{contrato}", "/contratos/{contrato}/checklists", "/contratos/{contrato}/agendamentos",
    "/imoveis", "/imoveis/{imovel}", "/imoveis/{imovel}/historico", "/checklists/{checklist}",
    "/checklists/{checklist}/pdf", "/dashboard",
])
def test_rota_de_leitura_nega_perfil_desconhecido(client, contrato, imovel, checklist, sem_o_portao, rota):
    caminho = rota.format(contrato=contrato.id, imovel=imovel.id, checklist=checklist.id)
    r = client.get(f"{API}{caminho}", headers=auth("qualquer"))
    assert r.status_code == 403, (caminho, r.text)
    assert "dados" not in r.json()


@pytest.mark.parametrize("rota", ["/contratos/{id}", "/contratos/{id}/checklists", "/imoveis/{id}",
                                  "/imoveis/{id}/historico", "/checklists/{id}/pdf"])
def test_id_inexistente_tambem_da_403(client, sem_o_portao, rota):
    """A checagem vem antes da busca: um perfil desconhecido não descobre quais IDs existem (404 contra 403)."""
    r = client.get(f"{API}{rota.format(id='00000000-0000-0000-0000-000000000000')}", headers=auth("qualquer"))
    assert r.status_code == 403, r.text
