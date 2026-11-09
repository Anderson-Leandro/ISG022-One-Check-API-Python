"""
DEBT-010 — Ramos de "não encontrado" e de validação das rotas (avaliação SPK-005)

Cada teste confere a resposta do ramo (status e mensagem) e, nas escritas, que o banco não mudou.
O que é de segurança saiu antes para SEC-032, SEC-033 e SEC-034.
"""

from datetime import date, datetime

import pytest

from app.models import AgendamentoVistoria, Contrato, Endereco, Imovel, ImovelComodo, Problema
from app.routers import agendamentos as rota_agendamentos
from app.routers import contratos as rota_contratos
from tests.conftest import auth, foto_do_banco, small_image_bytes

API = "/api/v1"
INEXISTENTE = "00000000-0000-0000-0000-000000000000"


def _nao_encontrado(r, mensagem):
    assert r.status_code == 404, r.text
    assert r.json()["erro"] == mensagem


@pytest.fixture
def problema(db, contrato):
    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    return pb


@pytest.fixture
def agendamento(db, contrato):
    return db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).first()


# --- _parse_datetime (agendamentos e contratos usam a mesma regra) ---


@pytest.mark.parametrize("modulo", [rota_agendamentos, rota_contratos])
class TestParseDatetime:
    def test_datetime_volta_igual(self, modulo):
        agora = datetime(2030, 1, 1, 10, 0)
        assert modulo._parse_datetime(agora) is agora

    def test_date_vira_meia_noite(self, modulo):
        assert modulo._parse_datetime(date(2030, 1, 1)) == datetime(2030, 1, 1)

    def test_z_vira_utc(self, modulo):
        assert modulo._parse_datetime("2030-01-01T10:00:00Z").utcoffset().total_seconds() == 0

    @pytest.mark.parametrize("valor", ["amanhã", 123, None])
    def test_invalido_levanta(self, modulo, valor):
        with pytest.raises(ValueError, match="Formato de data inválido"):
            modulo._parse_datetime(valor)


# --- Agendamentos ---


class TestAgendamentos:
    def test_alterar_inexistente(self, client, token_gestor):
        r = client.put(f"{API}/agendamentos/{INEXISTENTE}", json={"observacao": "x"}, headers=auth(token_gestor))
        _nao_encontrado(r, "Agendamento não encontrado")

    def test_data_em_formato_invalido_e_422_sem_gravar(self, client, db, agendamento, token_gestor):
        antes = foto_do_banco(db)
        r = client.put(
            f"{API}/agendamentos/{agendamento.id}", json={"data_agendada": "amanhã"}, headers=auth(token_gestor)
        )
        assert r.status_code == 422
        assert r.json()["erros"] == {"data_agendada": "Formato de data_agendada inválido"}
        assert foto_do_banco(db) == antes

    def test_so_a_observacao_muda_e_a_data_fica(self, client, db, agendamento, token_gestor):
        data = agendamento.data_agendada
        r = client.put(
            f"{API}/agendamentos/{agendamento.id}", json={"observacao": "Levar a chave"}, headers=auth(token_gestor)
        )
        assert r.status_code == 200, r.text
        db.expire_all()
        ag = db.get(AgendamentoVistoria, agendamento.id)
        assert (ag.observacao, ag.data_agendada) == ("Levar a chave", data)

    def test_so_o_tipo_muda_e_a_observacao_fica(self, client, db, agendamento, token_gestor):
        agendamento.observacao = "Nota"
        db.commit()
        novo = "encerramento" if agendamento.tipo == "inicial" else "inicial"
        r = client.put(f"{API}/agendamentos/{agendamento.id}", json={"tipo": novo}, headers=auth(token_gestor))
        assert r.status_code == 200, r.text
        db.expire_all()
        assert (
            db.get(AgendamentoVistoria, agendamento.id).tipo,
            db.get(AgendamentoVistoria, agendamento.id).observacao,
        ) == (novo, "Nota")

    def test_criar_com_data_invalida_e_422(self, client, db, contrato, token_gestor):
        antes = foto_do_banco(db)
        r = client.post(
            f"{API}/contratos/{contrato.id}/agendamentos",
            json={"tipo": "inicial", "data_agendada": "amanhã"},
            headers=auth(token_gestor),
        )
        assert r.status_code == 422
        assert "data_agendada" in r.json()["erros"]
        assert foto_do_banco(db) == antes


# --- Problemas ---


class TestProblemas:
    @pytest.mark.parametrize(
        "metodo,sufixo,corpo",
        [
            ("get", "", None),
            ("delete", "", None),
            ("patch", "/status", {"status": "resolvido"}),
            ("post", "/atualizacoes", {"descricao": "Texto do comentário"}),
            ("get", "/atualizacoes", None),
        ],
    )
    def test_inexistente(self, client, token_gestor, metodo, sufixo, corpo):
        r = client.request(
            metodo.upper(), f"{API}/problemas/{INEXISTENTE}{sufixo}", headers=auth(token_gestor), json=corpo
        )
        _nao_encontrado(r, "Problema não encontrado")

    def test_problema_de_contrato_excluido_responde_404_do_contrato(
        self, client, db, problema, contrato, user_admin, token_gestor
    ):
        from app.exclusao import marcar_excluido

        marcar_excluido(db.get(Contrato, contrato.id), user_admin)
        db.commit()
        r = client.get(f"{API}/problemas/{problema.id}", headers=auth(token_gestor))
        _nao_encontrado(r, "Contrato não encontrado")

    @pytest.mark.parametrize("corpo", ["isto não é json", "{"])
    def test_status_com_corpo_que_nao_e_json_e_422(self, client, db, problema, token_gestor, corpo):
        antes = foto_do_banco(db)
        r = client.patch(
            f"{API}/problemas/{problema.id}/status",
            content=corpo,
            headers={**auth(token_gestor), "Content-Type": "application/json"},
        )
        assert r.status_code == 422
        assert r.json()["erros"] == {"status": "Status inválido"}
        assert foto_do_banco(db) == antes

    def test_comentario_com_corpo_que_nao_e_json_e_422(self, client, db, problema, token_gestor):
        antes = foto_do_banco(db)
        r = client.post(
            f"{API}/problemas/{problema.id}/atualizacoes",
            content="{",
            headers={**auth(token_gestor), "Content-Type": "application/json"},
        )
        assert r.status_code == 422
        assert "descricao" in r.json()["erros"]
        assert foto_do_banco(db) == antes

    def test_comentario_multipart_sem_foto(self, client, db, problema, token_gestor):
        r = client.post(
            f"{API}/problemas/{problema.id}/atualizacoes",
            data={"descricao": "Comentário sem foto"},
            files={"campo": ("x.txt", b"", "text/plain")},
            headers=auth(token_gestor),
        )
        assert r.status_code == 201, r.text
        assert r.json()["dados"]["foto_url"] is None

    def test_comentario_com_foto_grande_demais_e_422(self, client, db, problema, token_gestor, monkeypatch):
        from app.routers import problemas as rota

        monkeypatch.setattr(rota, "MAX_UPLOAD_MB", 0)
        antes = foto_do_banco(db)
        r = client.post(
            f"{API}/problemas/{problema.id}/atualizacoes",
            data={"descricao": "Comentário com foto"},
            files={"foto": ("a.png", small_image_bytes(), "image/png")},
            headers=auth(token_gestor),
        )
        assert r.status_code == 422
        assert "foto" in r.json()["erros"]
        assert foto_do_banco(db) == antes


# --- Contratos ---


class TestContratos:
    @pytest.mark.parametrize("acao", ["encerrar", "cancelar"])
    def test_encerrar_ou_cancelar_inexistente(self, client, token_gestor, acao):
        r = client.post(f"{API}/contratos/{INEXISTENTE}/{acao}", headers=auth(token_gestor))
        _nao_encontrado(r, "Contrato não encontrado")

    def test_excluir_inexistente(self, client, token_gestor):
        _nao_encontrado(
            client.delete(f"{API}/contratos/{INEXISTENTE}", headers=auth(token_gestor)), "Contrato não encontrado"
        )

    def test_excluir_contrato_ativo_sem_registros_libera_o_imovel(
        self, client, db, imovel, user_locatario_2, token_gestor
    ):
        ct = Contrato(
            imovel_id=imovel.id,
            locatario_id=user_locatario_2.id,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            status="ativo",
        )
        imovel.status = "locado"
        db.add(ct)
        db.commit()
        r = client.delete(f"{API}/contratos/{ct.id}", headers=auth(token_gestor))
        assert r.status_code == 200, r.text
        db.expire_all()
        assert db.get(Imovel, imovel.id).status == "disponivel"

    def test_criar_com_locatario_inexistente(self, client, db, token_gestor):
        im = Imovel(tipo="casa", status="disponivel", garagem=False, garagem_vagas=0)
        db.add(im)
        db.commit()
        corpo = {"imovel_id": im.id, "locatario_id": INEXISTENTE, "data_inicio": "2026-01-01", "data_fim": "2026-12-31"}
        antes = foto_do_banco(db)
        _nao_encontrado(
            client.post(f"{API}/contratos", json=corpo, headers=auth(token_gestor)), "Locatário não encontrado"
        )
        assert foto_do_banco(db) == antes

    def test_criar_em_imovel_com_contrato_ativo_e_status_desatualizado(
        self, client, db, contrato, imovel, user_locatario_2, token_gestor
    ):
        imovel.status = "disponivel"  # status fora de sincronia: a trava pelo contrato ativo ainda vale
        db.commit()
        corpo = {
            "imovel_id": imovel.id,
            "locatario_id": user_locatario_2.id,
            "data_inicio": "2026-01-01",
            "data_fim": "2026-12-31",
        }
        antes = foto_do_banco(db)
        r = client.post(f"{API}/contratos", json=corpo, headers=auth(token_gestor))
        assert r.status_code == 409
        assert r.json()["erro"] == "Este imóvel já possui um contrato ativo"
        assert foto_do_banco(db) == antes

    def test_problema_com_corpo_que_nao_e_json_e_422(self, client, db, contrato, token_gestor):
        """O corpo que não é JSON vale como vazio: o 422 é o do título obrigatório, sem erro 500."""
        antes = foto_do_banco(db)
        r = client.post(
            f"{API}/contratos/{contrato.id}/problemas",
            content="{",
            headers={**auth(token_gestor), "Content-Type": "application/json"},
        )
        assert r.status_code == 422
        assert "titulo" in r.json()["erros"]
        assert foto_do_banco(db) == antes

    def test_problema_com_foto_url_de_fora_e_422(self, client, db, contrato, token_gestor):
        antes = foto_do_banco(db)
        r = client.post(
            f"{API}/contratos/{contrato.id}/problemas",
            json={"titulo": "Vazamento", "foto_url": "https://exemplo.com/a.png"},
            headers=auth(token_gestor),
        )
        assert r.status_code == 422
        assert r.json()["erros"] == {"foto_url": "Envie a foto pelo upload da API"}
        assert foto_do_banco(db) == antes

    def test_problema_multipart_com_campos_opcionais(self, client, contrato, token_gestor):
        r = client.post(
            f"{API}/contratos/{contrato.id}/problemas",
            data={"titulo": "Porta empenada", "descricao": " Não fecha ", "prioridade": "alta", "status": "aberto"},
            files={"foto": ("a.png", small_image_bytes(), "image/png")},
            headers=auth(token_gestor),
        )
        assert r.status_code == 201, r.text
        dados = r.json()["dados"]
        assert (dados["descricao"], dados["prioridade"]) == ("Não fecha", "alta")
        assert dados["foto_url"]

    def test_problema_multipart_com_foto_grande_demais_e_422(self, client, db, contrato, token_gestor, monkeypatch):
        monkeypatch.setattr(rota_contratos, "MAX_UPLOAD_MB", 0)
        antes = foto_do_banco(db)
        r = client.post(
            f"{API}/contratos/{contrato.id}/problemas",
            data={"titulo": "Porta empenada"},
            files={"foto": ("a.png", small_image_bytes(), "image/png")},
            headers=auth(token_gestor),
        )
        assert r.status_code == 422
        assert "foto" in r.json()["erros"]
        assert foto_do_banco(db) == antes


# --- Imóveis ---


class TestImoveis:
    @pytest.mark.parametrize(
        "metodo,sufixo,corpo",
        [
            ("get", "/endereco", None),
            ("get", "/comodos", None),
            ("post", "/comodos", {"tipo": "quarto"}),
            ("put", "/comodos/c1", {"tipo": "sala"}),
            ("delete", "/comodos/c1", None),
        ],
    )
    def test_imovel_inexistente(self, client, token_gestor, metodo, sufixo, corpo):
        r = client.request(
            metodo.upper(), f"{API}/imoveis/{INEXISTENTE}{sufixo}", headers=auth(token_gestor), json=corpo
        )
        _nao_encontrado(r, "Imóvel não encontrado")

    @pytest.mark.parametrize("metodo,corpo", [("put", {"tipo": "sala"}), ("delete", None)])
    def test_comodo_inexistente(self, client, imovel, token_gestor, metodo, corpo):
        r = client.request(
            metodo.upper(), f"{API}/imoveis/{imovel.id}/comodos/{INEXISTENTE}", headers=auth(token_gestor), json=corpo
        )
        _nao_encontrado(r, "Cômodo não encontrado")

    def test_alterar_comodo_so_a_descricao(self, client, db, imovel, token_gestor):
        c = ImovelComodo(imovel_id=imovel.id, tipo="quarto", nome="Quarto 1")
        db.add(c)
        db.commit()
        r = client.put(
            f"{API}/imoveis/{imovel.id}/comodos/{c.id}", json={"descricao": "Com armário"}, headers=auth(token_gestor)
        )
        assert r.status_code == 200, r.text
        db.expire_all()
        assert (db.get(ImovelComodo, c.id).tipo, db.get(ImovelComodo, c.id).descricao) == ("quarto", "Com armário")

    def test_endereco_com_coordenadas_nao_consulta_o_geocoding(self, client, db, imovel, token_gestor, monkeypatch):
        from app.routers import imoveis as rota

        chamadas = []
        monkeypatch.setattr(rota, "buscar_coordenadas", lambda *a: chamadas.append(a))
        corpo = {"rua": "Rua A", "cidade": "Recife", "estado": "PE", "latitude": -8.05, "longitude": -34.9}
        r = client.post(f"{API}/imoveis/{imovel.id}/endereco", json=corpo, headers=auth(token_gestor))
        assert r.status_code == 200, r.text
        assert chamadas == []

    def test_alterar_endereco_sem_coordenadas_mantem_as_gravadas(self, client, db, imovel, token_gestor, monkeypatch):
        from app.routers import imoveis as rota

        monkeypatch.setattr(rota, "buscar_coordenadas", lambda *a: None)
        corpo = {"rua": "Rua A", "cidade": "Recife", "estado": "PE", "latitude": -8.05, "longitude": -34.9}
        assert (
            client.post(f"{API}/imoveis/{imovel.id}/endereco", json=corpo, headers=auth(token_gestor)).status_code
            == 200
        )
        r = client.put(
            f"{API}/imoveis/{imovel.id}/endereco",
            json={"rua": "Rua B", "cidade": "Recife", "estado": "PE"},
            headers=auth(token_gestor),
        )
        assert r.status_code == 200, r.text
        db.expire_all()
        end = db.query(Endereco).filter(Endereco.imovel_id == imovel.id).one()
        assert (end.rua, end.latitude, end.longitude) == ("Rua B", -8.05, -34.9)

    def test_alterar_imovel_cria_o_endereco_que_faltava(self, client, db, imovel, token_gestor, monkeypatch):
        from app.routers import imoveis as rota

        monkeypatch.setattr(rota, "buscar_coordenadas", lambda *a: None)
        assert db.query(Endereco).filter(Endereco.imovel_id == imovel.id).count() == 0  # a fixture não tem endereço
        corpo = {"endereco": {"rua": "Rua C", "cidade": "Olinda", "estado": "PE"}}
        r = client.put(f"{API}/imoveis/{imovel.id}", json=corpo, headers=auth(token_gestor))
        assert r.status_code == 200, r.text
        db.expire_all()
        assert db.query(Endereco).filter(Endereco.imovel_id == imovel.id).one().rua == "Rua C"

    def test_excluir_imovel_sem_endereco(self, client, db, token_gestor):
        im = Imovel(tipo="casa", status="disponivel", garagem=False, garagem_vagas=0)
        db.add(im)
        db.commit()
        r = client.delete(f"{API}/imoveis/{im.id}", headers=auth(token_gestor))
        assert r.status_code == 200, r.text
        db.expire_all()
        assert db.get(Imovel, im.id).ativo is False

    def test_historico_de_imovel_sem_contratos_para_a_equipe(self, client, db, token_gestor):
        im = Imovel(tipo="casa", status="disponivel", garagem=False, garagem_vagas=0)
        db.add(im)
        db.commit()
        r = client.get(f"{API}/imoveis/{im.id}/historico", headers=auth(token_gestor))
        assert r.status_code == 200, r.text
        assert r.json()["dados"] == {"imovel_id": im.id, "eventos": []}
