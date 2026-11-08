"""
Fase 2.3 — Testes de integração das rotas de imóveis

Rotas cobertas:
  GET    /api/v1/imoveis
  POST   /api/v1/imoveis
  GET    /api/v1/imoveis/{id}
  PUT    /api/v1/imoveis/{id}
  GET    /api/v1/imoveis/{id}/endereco
  POST   /api/v1/imoveis/{id}/endereco   (upsert)
  PUT    /api/v1/imoveis/{id}/endereco   (upsert)
  GET    /api/v1/imoveis/{id}/comodos
"""
from tests.conftest import auth, foto_do_banco

BASE = "/api/v1/imoveis"

_ENDERECO = {
    "rua": "Rua das Flores",
    "numero": "100",
    "bairro": "Centro",
    "cidade": "Curitiba",
    "estado": "pr",
    "cep": "80000-000",
}


# ── GET /imoveis (listagem) ───────────────────────────────────────────────────────

class TestListImoveis:
    def test_admin_lista_todos(self, client, imovel, token_admin):
        r = client.get(BASE, headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert any(i["id"] == imovel.id for i in data["dados"])

    def test_paginacao_presente(self, client, imovel, token_admin):
        r = client.get(BASE, headers=auth(token_admin))
        data = r.json()
        assert "paginacao" in data
        assert data["paginacao"]["total"] >= 1

    def test_filtra_por_status(self, client, imovel, token_admin):
        r = client.get(f"{BASE}?status=disponivel", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        for i in data["dados"]:
            assert i["status"] == "disponivel"

    def test_com_endereco_inclui_campo(self, client, imovel, token_admin):
        r = client.get(f"{BASE}?com_endereco=true", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        for i in data["dados"]:
            assert "endereco" in i

    def test_locatario_ve_apenas_seus_imoveis(self, client, contrato, token_locatario):
        # contrato fixture associa imovel ao user_locatario
        r = client.get(BASE, headers=auth(token_locatario))
        data = r.json()
        assert data["sucesso"] is True
        ids = [i["id"] for i in data["dados"]]
        assert contrato.imovel_id in ids

    def test_vistoriador_ve_apenas_imoveis_com_checklist(self, client, checklist, token_vistoriador):
        r = client.get(BASE, headers=auth(token_vistoriador))
        data = r.json()
        assert data["sucesso"] is True
        # Deve conter o imóvel vinculado ao checklist
        assert len(data["dados"]) >= 1

    def test_sem_autenticacao_retorna_401(self, client):
        r = client.get(BASE)
        assert r.status_code == 401


# ── POST /imoveis ─────────────────────────────────────────────────────────────────

class TestCreateImovel:
    def test_cria_imovel_campos_obrigatorios(self, client, token_admin):
        r = client.post(
            BASE,
            json={"tipo": "apartamento"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "apartamento"
        assert data["dados"]["id"] is not None

    def test_cria_imovel_com_todos_campos(self, client, token_admin):
        r = client.post(
            BASE,
            json={
                "tipo": "casa",
                "codigo": "CASA-001",
                "titulo": "Casa com jardim",
                "tamanho": "150m²",
                "garagem": True,
                "garagem_vagas": 2,
                "status": "disponivel",
                "observacoes": "Ótima localização",
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["codigo"] == "CASA-001"
        assert data["dados"]["garagem"] is True
        assert data["dados"]["garagem_vagas"] == 2

    def test_criacao_gera_comodos_padrao(self, client, db, token_admin):
        from app.models import ImovelComodo
        r = client.post(BASE, json={"tipo": "casa"}, headers=auth(token_admin))
        imovel_id = r.json()["dados"]["id"]
        comodos = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel_id).all()
        assert len(comodos) == 4

    def test_sem_autenticacao_retorna_401(self, client, db):
        banco_antes = foto_do_banco(db)
        r = client.post(BASE, json={"tipo": "apartamento"})
        assert r.status_code == 401
        assert foto_do_banco(db) == banco_antes, "a requisição negada gravou no banco"


# ── GET /imoveis/{id} ─────────────────────────────────────────────────────────────

class TestGetImovel:
    def test_retorna_imovel_com_endereco(self, client, imovel, token_admin):
        r = client.get(f"{BASE}/{imovel.id}", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["id"] == imovel.id
        assert "endereco" in data["dados"]

    def test_id_inexistente_retorna_falha(self, client, token_admin):
        r = client.get(f"{BASE}/id-invalido", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "encontrado" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client, imovel):
        r = client.get(f"{BASE}/{imovel.id}")
        assert r.status_code == 401


# ── PUT /imoveis/{id} ─────────────────────────────────────────────────────────────

class TestUpdateImovel:
    def test_atualiza_status(self, client, imovel, token_admin):
        r = client.put(
            f"{BASE}/{imovel.id}",
            json={"status": "locado"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["status"] == "locado"

    def test_atualiza_multiplos_campos(self, client, imovel, token_admin):
        r = client.put(
            f"{BASE}/{imovel.id}",
            json={"titulo": "Novo Título", "garagem": True, "garagem_vagas": 1},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["titulo"] == "Novo Título"
        assert data["dados"]["garagem"] is True

    def test_id_inexistente_retorna_falha(self, client, token_admin):
        r = client.put(
            f"{BASE}/id-invalido",
            json={"status": "disponivel"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, db, imovel):
        banco_antes = foto_do_banco(db)
        r = client.put(f"{BASE}/{imovel.id}", json={"status": "disponivel"})
        assert r.status_code == 401
        assert foto_do_banco(db) == banco_antes, "a requisição negada gravou no banco"


# ── GET /imoveis/{id}/endereco ────────────────────────────────────────────────────

class TestGetEndereco:
    def test_retorna_endereco_existente(self, client, db, imovel, token_admin):
        from app.models import Endereco
        end = Endereco(imovel_id=imovel.id, **{k: v for k, v in _ENDERECO.items() if k != "estado"}, estado="PR")
        db.add(end)
        db.flush()

        r = client.get(f"{BASE}/{imovel.id}/endereco", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["cidade"] == "Curitiba"
        assert data["dados"]["estado"] == "PR"

    def test_sem_endereco_retorna_falha(self, client, imovel, token_admin):
        r = client.get(f"{BASE}/{imovel.id}/endereco", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "encontrado" in data["erro"].lower()

    def test_sem_autenticacao_retorna_401(self, client, imovel):
        r = client.get(f"{BASE}/{imovel.id}/endereco")
        assert r.status_code == 401


# ── POST/PUT /imoveis/{id}/endereco (upsert) ──────────────────────────────────────

class TestUpsertEndereco:
    def test_cria_endereco_via_post(self, client, imovel, token_admin):
        r = client.post(
            f"{BASE}/{imovel.id}/endereco",
            json=_ENDERECO,
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["cidade"] == "Curitiba"
        assert data["dados"]["estado"] == "PR"  # estado normalizado para uppercase

    def test_atualiza_endereco_via_put(self, client, imovel, token_admin):
        # Primeiro cria
        client.post(f"{BASE}/{imovel.id}/endereco", json=_ENDERECO, headers=auth(token_admin))
        # Depois atualiza
        r = client.put(
            f"{BASE}/{imovel.id}/endereco",
            json={**_ENDERECO, "cidade": "São Paulo", "estado": "SP"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["cidade"] == "São Paulo"
        assert data["dados"]["estado"] == "SP"

    def test_estado_normalizado_para_uppercase(self, client, imovel, token_admin):
        r = client.post(
            f"{BASE}/{imovel.id}/endereco",
            json={**_ENDERECO, "estado": "sp"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["dados"]["estado"] == "SP"

    def test_imovel_inexistente_retorna_falha(self, client, token_admin):
        r = client.post(
            f"{BASE}/id-invalido/endereco",
            json=_ENDERECO,
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is False

    def test_sem_autenticacao_retorna_401(self, client, db, imovel):
        banco_antes = foto_do_banco(db)
        r = client.post(f"{BASE}/{imovel.id}/endereco", json=_ENDERECO)
        assert r.status_code == 401
        assert foto_do_banco(db) == banco_antes, "a requisição negada gravou no banco"


# ── GET /imoveis/{id}/comodos ─────────────────────────────────────────────────────

class TestListComodos:
    def test_lista_comodos_do_imovel(self, client, imovel, token_admin):
        r = client.get(f"{BASE}/{imovel.id}/comodos", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert len(data["dados"]) == 4
        tipos = {c["tipo"] for c in data["dados"]}
        assert tipos == {"sala", "cozinha", "quarto", "banheiro"}

    def test_comodos_ordenados_por_tipo(self, client, imovel, token_admin):
        r = client.get(f"{BASE}/{imovel.id}/comodos", headers=auth(token_admin))
        tipos = [c["tipo"] for c in r.json()["dados"]]
        assert tipos == sorted(tipos)

    def test_cria_comodos_padrao_se_nao_existirem(self, client, db, token_admin):
        from app.models import Imovel, ImovelComodo
        im = Imovel(tipo="sala_comercial", status="disponivel", garagem=False, garagem_vagas=0)
        db.add(im)
        db.flush()
        # Sem cômodos criados
        count = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == im.id).count()
        assert count == 0

        r = client.get(f"{BASE}/{im.id}/comodos", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is True
        assert len(data["dados"]) == 4

    def test_sem_autenticacao_retorna_401(self, client, imovel):
        r = client.get(f"{BASE}/{imovel.id}/comodos")
        assert r.status_code == 401


# ── Criação e Atualização Atômica com Endereço ────────────────────────────────────

class TestImovelComEnderecoAtomico:
    def test_cria_imovel_com_endereco_aninhado(self, client, token_admin):
        r = client.post(
            BASE,
            json={
                "tipo": "apartamento",
                "tamanho": "75m²",
                "endereco": {
                    "rua": "Av Paulista",
                    "numero": "1000",
                    "bloco": "B",
                    "andar": "10",
                    "cidade": "São Paulo",
                    "estado": "SP",
                    "cep": "01310-100",
                },
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert "endereco" in data["dados"]
        assert data["dados"]["endereco"]["rua"] == "Av Paulista"
        assert data["dados"]["endereco"]["bloco"] == "B"
        assert data["dados"]["endereco"]["andar"] == "10"

    def test_atualiza_imovel_com_endereco_aninhado(self, client, imovel, token_admin):
        r = client.put(
            f"{BASE}/{imovel.id}",
            json={
                "tipo": "cobertura",
                "endereco": {
                    "rua": "Rua Nova",
                    "numero": "500",
                    "cidade": "Curitiba",
                    "estado": "PR",
                    "cep": "80000-100",
                },
            },
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "cobertura"
        assert data["dados"]["endereco"]["rua"] == "Rua Nova"


# ── DELETE /imoveis/{id} (Soft Delete) ───────────────────────────────────────────

class TestDeleteImovel:
    def test_admin_exclui_imovel_sucesso(self, client, db, imovel, token_admin):
        r = client.delete(f"{BASE}/{imovel.id}", headers=auth(token_admin))
        assert r.json()["sucesso"] is True

        db.refresh(imovel)
        assert imovel.ativo is False

    def test_bloqueia_exclusao_imovel_locado(self, client, db, imovel, token_admin):
        imovel.status = "locado"
        db.commit()

        r = client.delete(f"{BASE}/{imovel.id}", headers=auth(token_admin))
        data = r.json()
        assert data["sucesso"] is False
        assert "locado" in data["erro"].lower()

    def test_excluir_imovel_inexistente(self, client, token_admin):
        r = client.delete(f"{BASE}/00000000-0000-0000-0000-000000000000", headers=auth(token_admin))
        assert r.json()["sucesso"] is False


# ── Controle de Acesso por Locatário ─────────────────────────────────────────────

class TestAcessoLocatarioImovel:
    def test_locatario_sem_contrato_recebe_403_no_get_imovel(self, client, imovel, token_locatario):
        r = client.get(f"{BASE}/{imovel.id}", headers=auth(token_locatario))
        assert r.status_code == 403

    def test_locatario_com_contrato_acessa_imovel(self, client, contrato, token_locatario):
        r = client.get(f"{BASE}/{contrato.imovel_id}", headers=auth(token_locatario))
        assert r.status_code == 200
        assert r.json()["sucesso"] is True


# ── CRUD Completo de Cômodos ──────────────────────────────────────────────────────

class TestComodosCrud:
    def test_criar_comodo(self, client, imovel, token_admin):
        r = client.post(
            f"{BASE}/{imovel.id}/comodos",
            json={"tipo": "varanda", "descricao": "Varanda gourmet"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "varanda"
        assert data["dados"]["descricao"] == "Varanda gourmet"

    def test_atualizar_comodo(self, client, db, imovel, token_admin):
        from app.models import ImovelComodo
        c = ImovelComodo(imovel_id=imovel.id, tipo="quarto_antigo")
        db.add(c)
        db.commit()

        r = client.put(
            f"{BASE}/{imovel.id}/comodos/{c.id}",
            json={"tipo": "suite_master", "descricao": "Com closet"},
            headers=auth(token_admin),
        )
        data = r.json()
        assert data["sucesso"] is True
        assert data["dados"]["tipo"] == "suite_master"
        assert data["dados"]["descricao"] == "Com closet"

    def test_excluir_comodo(self, client, db, imovel, token_admin):
        from app.models import ImovelComodo
        c = ImovelComodo(imovel_id=imovel.id, tipo="despensa")
        db.add(c)
        db.commit()

        r = client.delete(f"{BASE}/{imovel.id}/comodos/{c.id}", headers=auth(token_admin))
        assert r.json()["sucesso"] is True

        # Verificar remoção no banco
        assert db.query(ImovelComodo).filter(ImovelComodo.id == c.id).first() is None
