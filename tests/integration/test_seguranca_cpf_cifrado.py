"""
SEC-031 — CPF cifrado em repouso (ADR-0014, R-014, LGPD art. 46)

- No banco (e num backup), a coluna usuarios.cpf guarda um token Fernet, não o CPF.
- A chave vem de CPF_CHAVES, fora do banco; a primeira cifra, todas decifram.
- Rotação: com a nova na frente, a inicialização recifra os CPFs com ela; depois a antiga sai.
- Um CPF ainda em texto (banco de antes da mudança) é cifrado na inicialização.
- As respostas da API não mudam.
"""

import pytest
from sqlalchemy import text

from app.config import CPF_CHAVES
from app.cpf_cifrado import Cifra, cifrar_cpfs_em_texto, rotacionar
from app.models import Usuario
from tests.conftest import auth

USUARIOS = "/api/v1/usuarios"
CPF = "529.982.247-25"
NOVA = "chave-nova-do-cpf-para-o-teste-de-rotacao-0001"
ANTIGA = "chave-antiga-do-cpf-para-o-teste-de-rotacao-02"


def _bruto(db, usuario_id):
    return db.execute(text("SELECT cpf FROM usuarios WHERE id = :id"), {"id": usuario_id}).scalar()


@pytest.fixture
def com_cpf(db, user_locatario):
    user_locatario.cpf = CPF
    db.commit()
    return user_locatario


class TestEmRepouso:
    def test_banco_guarda_o_token_e_nao_o_cpf(self, db, com_cpf):
        bruto = _bruto(db, com_cpf.id)
        assert bruto.startswith("gAAAAA")
        assert "529" not in bruto and "98224725" not in bruto.replace(".", "").replace("-", "")

    def test_cada_gravacao_gera_um_token_diferente(self, db, com_cpf, user_gestor):
        user_gestor.cpf = CPF
        db.commit()
        assert _bruto(db, com_cpf.id) != _bruto(db, user_gestor.id)

    def test_criacao_pela_api_grava_cifrado(self, client, db, token_admin):
        body = {
            "nome": "N",
            "email": "n@test.com",
            "senha": "Vistoria-Casa-42",
            "role": "locatario",
            "cpf": "52998224725",
        }
        r = client.post(USUARIOS, json=body, headers=auth(token_admin))
        assert r.status_code in (200, 201), r.text
        assert _bruto(db, r.json()["dados"]["id"]).startswith("gAAAAA")

    def test_sem_cpf_continua_nulo(self, db, user_locatario):
        assert _bruto(db, user_locatario.id) is None


class TestRespostasNaoMudam:
    def test_proprio_usuario_ve_o_cpf_completo(self, client, com_cpf, token_locatario):
        assert client.get(f"{USUARIOS}/me", headers=auth(token_locatario)).json()["dados"]["cpf"] == CPF

    def test_orm_le_o_cpf_decifrado(self, db, com_cpf):
        db.expire_all()
        assert db.get(Usuario, com_cpf.id).cpf == CPF


class TestMigracaoERotacao:
    def test_inicializacao_cifra_o_cpf_em_texto(self, db, user_locatario):
        from app.database import ensure_schema_updates

        db.execute(text("UPDATE usuarios SET cpf = :c WHERE id = :id"), {"c": CPF, "id": user_locatario.id})
        db.commit()

        ensure_schema_updates()

        assert _bruto(db, user_locatario.id).startswith("gAAAAA")
        db.expire_all()
        assert db.get(Usuario, user_locatario.id).cpf == CPF

    def test_rotacao_recifra_com_a_chave_nova(self, db, user_locatario):
        uid = user_locatario.id  # depois do commit, ler o objeto recarregaria o CPF pela ORM
        antiga = Cifra([ANTIGA])
        db.execute(text("UPDATE usuarios SET cpf = :c WHERE id = :id"), {"c": antiga.cifrar(CPF), "id": uid})
        db.commit()
        # A chave dos testes também, para os outros usuários do banco (as fixtures)
        troca = Cifra([NOVA, ANTIGA, *CPF_CHAVES])

        try:
            with db.get_bind().begin() as conn:
                conferencia = rotacionar(conn, troca, aplicar=False)
            assert conferencia["recifrados"] >= 1 and conferencia["ilegiveis"] == []
            assert _bruto(db, uid).startswith("gAAAAA") and antiga.decifrar(_bruto(db, uid)) == CPF  # só contou

            with db.get_bind().begin() as conn:
                rotacionar(conn, troca)
            novo = _bruto(db, uid)
            assert Cifra([NOVA]).decifrar(novo) == CPF  # a antiga já pode sair de CPF_CHAVES
            with pytest.raises(RuntimeError):
                antiga.decifrar(novo)
            with db.get_bind().begin() as conn:
                assert rotacionar(conn, troca, aplicar=False)["recifrados"] == 0
        finally:
            # Volta à chave dos testes, para a limpeza das fixtures conseguir ler os usuários
            with db.get_bind().begin() as conn:
                rotacionar(conn, Cifra([*CPF_CHAVES, NOVA]))

    def test_cpf_ilegivel_aparece_na_conferencia_e_nao_e_regravado(self, db, user_locatario):
        uid = user_locatario.id
        desconhecido = Cifra(["chave-que-ninguem-tem-mais-0123456789abcdef"]).cifrar(CPF)
        db.execute(text("UPDATE usuarios SET cpf = :c WHERE id = :id"), {"c": desconhecido, "id": uid})
        db.commit()
        try:
            with db.get_bind().begin() as conn:
                r = rotacionar(conn)
            assert r["ilegiveis"] == [uid]
            assert _bruto(db, uid) == desconhecido
        finally:
            db.execute(text("UPDATE usuarios SET cpf = NULL WHERE id = :id"), {"id": uid})
            db.commit()

    def test_inicializacao_nao_decifra_nem_cai_com_cpf_ilegivel(self, db, user_locatario):
        from app.database import ensure_schema_updates

        uid = user_locatario.id
        desconhecido = Cifra(["chave-que-ninguem-tem-mais-0123456789abcdef"]).cifrar(CPF)
        db.execute(text("UPDATE usuarios SET cpf = :c WHERE id = :id"), {"c": desconhecido, "id": uid})
        db.commit()
        try:
            ensure_schema_updates()  # não levanta: a inicialização só cifra o que está em texto
            assert _bruto(db, uid) == desconhecido
        finally:
            db.execute(text("UPDATE usuarios SET cpf = NULL WHERE id = :id"), {"id": uid})
            db.commit()

    def test_segunda_inicializacao_nao_regrava(self, db, com_cpf):
        with db.get_bind().begin() as conn:
            cifrar_cpfs_em_texto(conn)
        antes = _bruto(db, com_cpf.id)
        with db.get_bind().begin() as conn:
            assert cifrar_cpfs_em_texto(conn) == 0
        assert _bruto(db, com_cpf.id) == antes

    def test_chave_desconhecida_falha_em_vez_de_devolver_o_token(self):
        token = Cifra([ANTIGA]).cifrar(CPF)
        with pytest.raises(RuntimeError, match="CPF_CHAVES"):
            Cifra([NOVA]).decifrar(token)

    def test_qualquer_segredo_longo_serve_de_chave(self):
        c = Cifra(["segredo gerado pelo Render com + e / no meio=="])
        assert c.decifrar(c.cifrar(CPF)) == CPF


def test_postgres_alarga_a_coluna_antiga(db):
    """Num banco de antes da mudança, VARCHAR(14) não comporta o token: a inicialização alarga a coluna."""
    from app.cpf_cifrado import TAMANHO_COLUNA
    from app.database import engine, ensure_schema_updates

    if engine.dialect.name != "postgresql":
        pytest.skip("o SQLite não confere o tamanho da coluna; o CI roda este teste no PostgreSQL")
    db.execute(text("UPDATE usuarios SET cpf = NULL"))
    db.execute(text("ALTER TABLE usuarios ALTER COLUMN cpf TYPE VARCHAR(14)"))
    db.commit()

    ensure_schema_updates()

    tamanho = db.execute(
        text(
            "SELECT character_maximum_length FROM information_schema.columns WHERE table_name = 'usuarios' AND column_name = 'cpf'"
        )
    ).scalar()
    assert tamanho == TAMANHO_COLUNA
