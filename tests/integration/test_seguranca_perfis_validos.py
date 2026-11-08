"""
Segurança — DEBT-015: o perfil visualizador foi removido e perfis fora da lista são recusados (ADR-0009)

As regras de acesso de app/deps.py restringem só locatário e vistoriador e liberam os outros perfis. Um
perfil fora de ROLES gravado no banco (o antigo visualizador, um erro de digitação, um script) seria tratado
como admin/gestor. Por isso:
  - criar ou alterar um usuário com o perfil visualizador responde 422;
  - get_current_user recusa conta com perfil fora de ROLES (401), em qualquer rota autenticada;
  - o modelo Usuario não tem perfil padrão.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth import ROLES, create_access_token
from app.models import Usuario
from tests.conftest import _SENHA_HASH, auth, foto_do_banco

API = "/api/v1"


def test_visualizador_nao_e_mais_um_perfil():
    assert ROLES == {"admin", "gestor", "vistoriador", "locatario"}


class TestCriarOuAlterarComVisualizador:
    def test_criar_usuario_visualizador_responde_422(self, client, db, token_admin):
        antes = foto_do_banco(db)
        r = client.post(
            f"{API}/usuarios",
            json={"nome": "Leitor", "email": "leitor@test.com", "senha": "Leitura#Segura2026", "role": "visualizador"},
            headers=auth(token_admin),
        )
        assert r.status_code == 422, r.text
        assert r.json()["erros"] == {"role": "Perfil inválido"}
        assert foto_do_banco(db) == antes

    def test_alterar_para_visualizador_responde_422(self, client, db, user_locatario, token_admin):
        antes = foto_do_banco(db)
        r = client.put(f"{API}/usuarios/{user_locatario.id}", json={"role": "visualizador"}, headers=auth(token_admin))
        assert r.status_code == 422, r.text
        assert r.json()["erros"] == {"role": "Perfil inválido"}
        assert foto_do_banco(db) == antes


@pytest.fixture(params=["visualizador", "admn", ""])
def conta_com_perfil_fora_da_lista(request, db):
    u = Usuario(
        nome="Perfil Estranho",
        email=f"estranho{len(request.param)}@test.com",
        senha_hash=_SENHA_HASH,
        role=request.param,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u


class TestPerfilForaDaListaNaoAcessaNada:
    @pytest.mark.parametrize("rota", ["/usuarios/me", "/contratos", "/imoveis", "/dashboard"])
    def test_rota_autenticada_responde_401(self, client, conta_com_perfil_fora_da_lista, rota):
        u = conta_com_perfil_fora_da_lista
        r = client.get(f"{API}{rota}", headers=auth(create_access_token(u.id, u.role)))
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "Perfil de acesso inválido"
        assert "dados" not in r.json()

    def test_token_com_perfil_valido_nao_contorna_o_banco(self, client, conta_com_perfil_fora_da_lista):
        """O perfil que vale é o do banco, não o declarado no token."""
        u = conta_com_perfil_fora_da_lista
        r = client.get(f"{API}/contratos", headers=auth(create_access_token(u.id, "admin")))
        assert r.status_code == 401


def test_usuario_sem_perfil_nao_e_gravado(db):
    db.add(Usuario(nome="Sem Perfil", email="sem.perfil@test.com", senha_hash=_SENHA_HASH, ativo=True))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


class TestPerfilForaDaListaNaoAbreSessao:
    def test_login_com_senha_certa_e_recusado_como_credencial_invalida(self, client, conta_com_perfil_fora_da_lista):
        from tests.conftest import TEST_SENHA

        r = client.post(f"{API}/auth/login", json={"email": conta_com_perfil_fora_da_lista.email, "senha": TEST_SENHA})
        assert r.status_code == 401, r.text
        assert r.json() == {"sucesso": False, "erro": "Credenciais inválidas"}

    def test_refresh_token_existente_nao_renova(self, client, db, conta_com_perfil_fora_da_lista):
        from app.auth import create_refresh_token

        refresh = create_refresh_token(db, conta_com_perfil_fora_da_lista.id)
        r = client.post(f"{API}/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401, r.text
        assert "access_token" not in r.text
