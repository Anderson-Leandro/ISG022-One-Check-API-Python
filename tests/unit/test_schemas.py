"""
Fase 1.2 — Testes unitários de app/schemas.py

Grupos:
  - Helpers de resposta: ok(), fail()
  - Modelo Paginacao
  - Modelos de Auth (LoginRequest, MfaEnableRequest, RefreshRequest, ...)
  - Modelos de Usuário (UsuarioCreate, UsuarioUpdateMe, UsuarioUpdate)
  - Modelos de Imóvel (ImovelCreate, ImovelUpdate, EnderecoCreate)
  - Modelos de Contrato (ContratoCreate)
  - Modelos de Checklist (ChecklistCreate, AddChecklistItemRequest, ItemUpdateRequest)
  - Modelos de Problema (ProblemaCreate)
"""
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import (
    AddChecklistItemRequest,
    ChecklistCreate,
    ContratoCreate,
    EnderecoCreate,
    ImovelCreate,
    ImovelUpdate,
    ItemUpdateRequest,
    LoginRequest,
    MfaEnableRequest,
    MfaVerifyRequest,
    Paginacao,
    ProblemaCreate,
    RefreshRequest,
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioUpdateMe,
    fail,
    ok,
)


# ── ok() ─────────────────────────────────────────────────────────────────────────

def test_ok_sucesso_true():
    r = ok({"chave": "valor"})
    assert r["sucesso"] is True


def test_ok_dados_payload():
    payload = {"id": "123", "nome": "Teste"}
    r = ok(payload)
    assert r["dados"] == payload


def test_ok_dados_none():
    r = ok(None)
    assert r["sucesso"] is True
    assert r["dados"] is None


def test_ok_dados_lista():
    r = ok([1, 2, 3])
    assert r["dados"] == [1, 2, 3]


def test_ok_sem_paginacao_nao_inclui_chave():
    r = ok("qualquer")
    assert "paginacao" not in r


def test_ok_com_paginacao_dict():
    pag = {"total": 50, "pagina": 1, "itensPorPagina": 20}
    r = ok([], paginacao=pag)
    assert r["paginacao"] == pag


def test_ok_com_paginacao_model():
    pag = Paginacao(total=100, pagina=2, itensPorPagina=10)
    r = ok([], paginacao=pag)
    assert r["paginacao"] == {"total": 100, "pagina": 2, "itensPorPagina": 10}


def test_ok_paginacao_none_nao_inclui_chave():
    r = ok("dados", paginacao=None)
    assert "paginacao" not in r


# ── fail() ────────────────────────────────────────────────────────────────────────

def test_fail_sucesso_false():
    r = fail("mensagem de erro")
    assert r["sucesso"] is False


def test_fail_campo_erro():
    r = fail("algo deu errado")
    assert r["erro"] == "algo deu errado"


def test_fail_sem_erros_nao_inclui_chave():
    r = fail("erro")
    assert "erros" not in r


def test_fail_com_erros_lista():
    r = fail("inválido", erros=["campo obrigatório", "email inválido"])
    assert r["erros"] == ["campo obrigatório", "email inválido"]


def test_fail_com_erros_dict():
    r = fail("inválido", erros={"email": "já cadastrado"})
    assert r["erros"] == {"email": "já cadastrado"}


def test_fail_erros_none_explícito_nao_inclui_chave():
    r = fail("erro", erros=None)
    assert "erros" not in r


# ── Paginacao ─────────────────────────────────────────────────────────────────────

def test_paginacao_instancia_valida():
    p = Paginacao(total=100, pagina=1, itensPorPagina=20)
    assert p.total == 100
    assert p.pagina == 1
    assert p.itensPorPagina == 20


def test_paginacao_model_dump():
    p = Paginacao(total=5, pagina=1, itensPorPagina=5)
    d = p.model_dump()
    assert set(d.keys()) == {"total", "pagina", "itensPorPagina"}


# ── Auth ──────────────────────────────────────────────────────────────────────────

def test_login_request_valido():
    r = LoginRequest(email="user@test.com", senha="senha123")
    assert r.email == "user@test.com"
    assert r.senha == "senha123"


def test_mfa_verify_request_valido():
    r = MfaVerifyRequest(temp_token="token.qualquer.aqui", codigo="123456")
    assert r.temp_token == "token.qualquer.aqui"
    assert r.codigo == "123456"


def test_refresh_request_valido():
    r = RefreshRequest(refresh_token="raw-token-value")
    assert r.refresh_token == "raw-token-value"


class TestMfaEnableRequest:
    def test_valido(self):
        r = MfaEnableRequest(secret="A" * 16, codigo="123456")
        assert r.secret == "A" * 16
        assert r.codigo == "123456"

    def test_secret_min_length_ok(self):
        MfaEnableRequest(secret="A" * 16, codigo="123456")  # 16 chars — limite mínimo

    def test_secret_abaixo_do_minimo(self):
        with pytest.raises(ValidationError):
            MfaEnableRequest(secret="A" * 15, codigo="123456")  # 15 chars — inválido

    def test_secret_acima_do_maximo(self):
        with pytest.raises(ValidationError):
            MfaEnableRequest(secret="A" * 65, codigo="123456")  # 65 chars — inválido

    def test_secret_max_length_ok(self):
        MfaEnableRequest(secret="A" * 64, codigo="123456")  # 64 chars — limite máximo

    def test_codigo_exatamente_6_chars(self):
        MfaEnableRequest(secret="A" * 16, codigo="123456")

    def test_codigo_menos_de_6_chars(self):
        with pytest.raises(ValidationError):
            MfaEnableRequest(secret="A" * 16, codigo="12345")  # 5 chars

    def test_codigo_mais_de_6_chars(self):
        with pytest.raises(ValidationError):
            MfaEnableRequest(secret="A" * 16, codigo="1234567")  # 7 chars


# ── Usuário ───────────────────────────────────────────────────────────────────────

class TestUsuarioCreate:
    def test_valido(self):
        u = UsuarioCreate(nome="João", email="joao@test.com", senha="Vistoria-Casa-42", role="locatario")
        assert u.nome == "João"
        assert u.role == "locatario"

    def test_senha_minimo_10_chars_ok(self):
        UsuarioCreate(nome="A", email="a@b.com", senha="Kq8#vT2!mZ", role="locatario")

    def test_senha_abaixo_do_minimo(self):
        with pytest.raises(ValidationError):
            UsuarioCreate(nome="A", email="a@b.com", senha="Kq8#vT2!m", role="locatario")

    def test_cpf_opcional(self):
        u = UsuarioCreate(nome="A", email="a@b.com", senha="Kq8#vT2!mZ", role="locatario")
        assert u.cpf is None

    def test_cpf_preenchido(self):
        u = UsuarioCreate(nome="A", email="a@b.com", senha="Kq8#vT2!mZ", role="locatario", cpf="000.000.000-00")
        assert u.cpf == "000.000.000-00"


class TestUsuarioUpdateMe:
    def test_todos_campos_opcionais(self):
        u = UsuarioUpdateMe()
        assert u.nome is None
        assert u.senha_atual is None
        assert u.senha_nova is None

    def test_senha_nova_minimo_10_chars_ok(self):
        UsuarioUpdateMe(senha_nova="Kq8#vT2!mZ")

    def test_senha_nova_abaixo_do_minimo(self):
        with pytest.raises(ValidationError):
            UsuarioUpdateMe(senha_nova="Kq8#vT2!m")


class TestUsuarioUpdate:
    def test_todos_campos_opcionais(self):
        u = UsuarioUpdate()
        assert u.nome is None
        assert u.role is None
        assert u.senha is None
        assert u.mfa_enabled is None

    def test_senha_abaixo_do_minimo(self):
        with pytest.raises(ValidationError):
            UsuarioUpdate(senha="Kq8#vT2!m")

    def test_mfa_enabled_bool(self):
        u = UsuarioUpdate(mfa_enabled=False)
        assert u.mfa_enabled is False


# ── Imóvel ────────────────────────────────────────────────────────────────────────

class TestImovelCreate:
    def test_valido_apenas_tipo(self):
        im = ImovelCreate(tipo="apartamento")
        assert im.tipo == "apartamento"

    def test_defaults(self):
        im = ImovelCreate(tipo="casa")
        assert im.garagem is False
        assert im.garagem_vagas == 0
        assert im.status == "disponivel"
        assert im.codigo is None
        assert im.titulo is None

    def test_campos_opcionais_preenchidos(self):
        im = ImovelCreate(
            tipo="casa",
            codigo="C-001",
            titulo="Casa com jardim",
            tamanho="120m²",
            garagem=True,
            garagem_vagas=2,
            status="locado",
            observacoes="Observação",
        )
        assert im.garagem is True
        assert im.garagem_vagas == 2


class TestImovelUpdate:
    def test_todos_campos_opcionais(self):
        iu = ImovelUpdate()
        assert iu.tipo is None
        assert iu.status is None


class TestEnderecoCreate:
    def test_valido_campos_obrigatorios(self):
        e = EnderecoCreate(rua="Rua das Flores", cidade="São Paulo", estado="SP")
        assert e.rua == "Rua das Flores"
        assert e.cidade == "São Paulo"
        assert e.estado == "SP"

    def test_campos_opcionais_none(self):
        e = EnderecoCreate(rua="Rua X", cidade="Cidade Y", estado="MG")
        assert e.numero is None
        assert e.complemento is None
        assert e.bairro is None
        assert e.cep is None
        assert e.latitude is None
        assert e.longitude is None

    def test_com_coordenadas(self):
        e = EnderecoCreate(
            rua="Av. Paulista", cidade="São Paulo", estado="SP",
            latitude=-23.5630, longitude=-46.6543,
        )
        assert e.latitude == pytest.approx(-23.5630)
        assert e.longitude == pytest.approx(-46.6543)


# ── Contrato ──────────────────────────────────────────────────────────────────────

class TestContratoCreate:
    def test_valido(self):
        ct = ContratoCreate(
            imovel_id="imovel-uuid",
            locatario_id="locatario-uuid",
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 12, 31),
        )
        assert ct.imovel_id == "imovel-uuid"
        assert ct.data_inicio == date(2025, 1, 1)

    def test_valor_mensal_opcional(self):
        ct = ContratoCreate(
            imovel_id="x", locatario_id="y",
            data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31),
        )
        assert ct.valor_mensal is None

    def test_valor_mensal_preenchido(self):
        ct = ContratoCreate(
            imovel_id="x", locatario_id="y",
            data_inicio=date(2025, 1, 1), data_fim=date(2025, 12, 31),
            valor_mensal=1500.0,
        )
        assert ct.valor_mensal == 1500.0


# ── Checklist ─────────────────────────────────────────────────────────────────────

class TestChecklistCreate:
    def test_valido_sem_data_vistoria(self):
        ck = ChecklistCreate(tipo="inicial", vistoriador_id="vist-uuid")
        assert ck.tipo == "inicial"
        assert ck.data_vistoria is None

    def test_valido_com_data_vistoria(self):
        ck = ChecklistCreate(
            tipo="encerramento",
            vistoriador_id="vist-uuid",
            data_vistoria=date(2025, 6, 15),
        )
        assert ck.data_vistoria == date(2025, 6, 15)


class TestAddChecklistItemRequest:
    def test_valido(self):
        r = AddChecklistItemRequest(
            comodo_id="comodo-uuid",
            item_vistoria_id="item-uuid",
            estado="bom",
        )
        assert r.estado == "bom"
        assert r.observacao is None

    def test_com_observacao(self):
        r = AddChecklistItemRequest(
            comodo_id="c", item_vistoria_id="i",
            estado="ruim", observacao="Parede com umidade",
        )
        assert r.observacao == "Parede com umidade"


class TestItemUpdateRequest:
    def test_todos_campos_opcionais(self):
        r = ItemUpdateRequest()
        assert r.estado is None
        assert r.observacao is None

    def test_so_estado(self):
        r = ItemUpdateRequest(estado="otimo")
        assert r.estado == "otimo"

    def test_so_observacao(self):
        r = ItemUpdateRequest(observacao="Sem problemas")
        assert r.observacao == "Sem problemas"


# ── Problema ──────────────────────────────────────────────────────────────────────

class TestProblemaCreate:
    def test_valido_apenas_titulo(self):
        p = ProblemaCreate(titulo="Vazamento na torneira")
        assert p.titulo == "Vazamento na torneira"

    def test_prioridade_default(self):
        p = ProblemaCreate(titulo="X")
        assert p.prioridade == "normal"

    def test_status_default(self):
        p = ProblemaCreate(titulo="X")
        assert p.status == "aberto"

    def test_descricao_opcional(self):
        p = ProblemaCreate(titulo="X")
        assert p.descricao is None

    def test_prioridade_personalizada(self):
        p = ProblemaCreate(titulo="X", prioridade="urgente")
        assert p.prioridade == "urgente"

    def test_status_personalizado(self):
        p = ProblemaCreate(titulo="X", status="em_analise")
        assert p.status == "em_analise"

    def test_comodo_id_e_foto_url(self):
        p = ProblemaCreate(titulo="X", comodo_id="c-1", foto_url="/uploads/foto.jpg")
        assert p.comodo_id == "c-1"
        assert p.foto_url == "/uploads/foto.jpg"


# ── Aceite Checklist & Atualização Problema ───────────────────────────────────────

class TestAceiteChecklistSchemas:
    def test_aceite_checklist_request(self):
        from app.schemas import AceiteChecklistRequest
        r = AceiteChecklistRequest(motivo_rejeicao="Pintura descascando")
        assert r.motivo_rejeicao == "Pintura descascando"

    def test_aceite_checklist_out(self):
        from app.schemas import AceiteChecklistOut
        out = AceiteChecklistOut(
            id="a-1",
            checklist_id="ck-1",
            locatario_id="u-1",
            status="aceito",
            motivo_rejeicao=None,
        )
        assert out.status == "aceito"
        assert out.id == "a-1"


class TestAtualizacaoProblemaSchemas:
    def test_atualizacao_create(self):
        from app.schemas import AtualizacaoProblemaCreate
        a = AtualizacaoProblemaCreate(descricao="Técnico agendado", foto_url="foto.jpg")
        assert a.descricao == "Técnico agendado"
        assert a.foto_url == "foto.jpg"

    def test_atualizacao_out(self):
        from app.schemas import AtualizacaoProblemaOut
        a = AtualizacaoProblemaOut(
            id="at-1",
            problema_id="pb-1",
            autor_id="u-1",
            descricao="Resolvido",
            foto_url=None,
        )
        assert a.id == "at-1"
        assert a.descricao == "Resolvido"


class TestLogOutSchema:
    def test_log_out_com_payload_e_ip(self):
        from app.schemas import LogOut
        log = LogOut(
            id="l-1",
            acao="create",
            entidade="imovel",
            entidade_id="im-1",
            detalhes="Criado",
            payload={"tipo": "casa"},
            ip="127.0.0.1",
        )
        assert log.payload == {"tipo": "casa"}
        assert log.ip == "127.0.0.1"
