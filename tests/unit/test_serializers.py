"""
Fase 1.3 — Testes unitários de app/serializers.py

Estratégia:
  - Funções que só acessam atributos simples → instâncias de modelo ORM criadas
    em memória (sem banco), já que SQLAlchemy permite isso.
  - Funções que acessam relacionamentos (itens, fotos, endereco) → SimpleNamespace
    para evitar DetachedInstanceError em objetos desconectados do banco.
  - Funções que dependem de queries reais (paginate, log_operacao,
    ensure_default_comodos, get_comodos_for_checklist) → fixture db.
"""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models import (
    Imovel,
    ImovelComodo,
    ItemVistoria,
    LogOperacao,
    Usuario,
)
from app.serializers import (
    ensure_default_comodos,
    foto_url,
    get_comodos_for_checklist,
    log_operacao,
    paginate,
    serialize_checklist,
    serialize_comodo,
    serialize_contrato,
    serialize_endereco,
    serialize_foto,
    serialize_imovel,
    serialize_item,
    serialize_usuario,
)

# ── foto_url ──────────────────────────────────────────────────────────────────────


def test_foto_url_formato():
    assert foto_url("imagem.jpg") == "/api/v1/uploads/imagem.jpg"


def test_foto_url_nome_uuid():
    assert foto_url("abc123def456.png") == "/api/v1/uploads/abc123def456.png"


# ── serialize_foto ────────────────────────────────────────────────────────────────


def test_serialize_foto_campos():
    f = SimpleNamespace(id="foto-id-1", arquivo="foto.jpg")
    result = serialize_foto(f)
    assert result["id"] == "foto-id-1"
    assert result["url"] == "/api/v1/uploads/foto.jpg"


def test_serialize_foto_url_usa_foto_url():
    f = SimpleNamespace(id="x", arquivo="test.png")
    result = serialize_foto(f)
    assert result["url"] == foto_url("test.png")


# ── serialize_item ────────────────────────────────────────────────────────────────


def test_serialize_item_campos():
    foto = SimpleNamespace(id="f1", arquivo="foto.jpg")
    item = SimpleNamespace(
        id="item-id",
        checklist_id="ck-id",
        comodo_id="cm-id",
        item_vistoria_id="iv-id",
        estado="bom",
        observacao="ok",
        fotos=[foto],
    )
    result = serialize_item(item)
    assert result["id"] == "item-id"
    assert result["estado"] == "bom"
    assert len(result["fotos"]) == 1
    assert result["fotos"][0]["url"] == "/api/v1/uploads/foto.jpg"


def test_serialize_item_sem_fotos():
    item = SimpleNamespace(
        id="i",
        checklist_id="c",
        comodo_id="cm",
        item_vistoria_id="iv",
        estado=None,
        observacao=None,
        fotos=[],
    )
    result = serialize_item(item)
    assert result["fotos"] == []
    assert result["estado"] is None


# ── serialize_comodo ──────────────────────────────────────────────────────────────


def test_serialize_comodo_campos():
    c = ImovelComodo(
        id="cm-id",
        imovel_id="im-id",
        tipo="sala",
        descricao="Sala de estar",
        nome="Sala",
    )
    result = serialize_comodo(c)
    assert result == {
        "id": "cm-id",
        "imovel_id": "im-id",
        "tipo": "sala",
        "descricao": "Sala de estar",
        "nome": "Sala",
    }


def test_serialize_comodo_campos_opcionais_none():
    c = ImovelComodo(id="x", imovel_id="y", tipo="quarto")
    result = serialize_comodo(c)
    assert result["descricao"] is None
    assert result["nome"] is None


# ── serialize_endereco ────────────────────────────────────────────────────────────


def test_serialize_endereco_none_retorna_none():
    assert serialize_endereco(None) is None


def test_serialize_endereco_campos_obrigatorios():
    end = SimpleNamespace(
        rua="Rua das Flores",
        numero="10",
        complemento=None,
        bairro="Centro",
        cidade="São Paulo",
        estado="SP",
        cep="01000-000",
        latitude=None,
        longitude=None,
    )
    result = serialize_endereco(end)
    assert result["rua"] == "Rua das Flores"
    assert result["logradouro"] == "Rua das Flores"  # duplica rua como logradouro
    assert result["cidade"] == "São Paulo"
    assert result["estado"] == "SP"


def test_serialize_endereco_com_coordenadas():
    end = SimpleNamespace(
        rua="Av. Paulista",
        numero=None,
        complemento=None,
        bairro=None,
        cidade="SP",
        estado="SP",
        cep=None,
        latitude=-23.5630,
        longitude=-46.6543,
    )
    result = serialize_endereco(end)
    assert result["latitude"] == pytest.approx(-23.5630)
    assert result["longitude"] == pytest.approx(-46.6543)


def test_serialize_endereco_objeto_falsy_retorna_none():
    # Garante que qualquer objeto falsy retorna None (ex.: instância vazia)
    assert serialize_endereco(False) is None


# ── serialize_usuario ─────────────────────────────────────────────────────────────


def test_serialize_usuario_contem_todos_campos():
    u = Usuario(
        nome="Ana",
        email="ana@test.com",
        role="admin",
        senha_hash="h",
        mfa_enabled=True,
        mfa_secret="SECRET",
        cpf="529.982.247-25",
    )
    result = serialize_usuario(u)
    assert set(result.keys()) == {
        "id",
        "nome",
        "email",
        "role",
        "cpf",
        "mfa_enabled",
        "mfa_configurado",
        "mfa_ativo",
        "senha_expirada",
        "created_at",
    }


def test_serialize_usuario_mfa_ativo_true():
    u = Usuario(nome="A", email="a@t.com", role="admin", senha_hash="h", mfa_enabled=True, mfa_secret="SECRET")
    result = serialize_usuario(u)
    assert result["mfa_ativo"] is True
    assert result["mfa_configurado"] is True
    assert result["mfa_enabled"] is True


def test_serialize_usuario_mfa_ativo_false_sem_secret():
    u = Usuario(nome="A", email="a@t.com", role="admin", senha_hash="h", mfa_enabled=True, mfa_secret=None)
    result = serialize_usuario(u)
    assert result["mfa_ativo"] is False
    assert result["mfa_configurado"] is False


def test_serialize_usuario_mfa_ativo_false_disabled():
    u = Usuario(nome="A", email="a@t.com", role="locatario", senha_hash="h", mfa_enabled=False, mfa_secret="SECRET")
    result = serialize_usuario(u)
    assert result["mfa_ativo"] is False


def test_serialize_usuario_created_at_none_quando_sem_banco():
    u = Usuario(nome="A", email="a@t.com", role="locatario", senha_hash="h")
    result = serialize_usuario(u)
    assert result["created_at"] is None  # server_default só aplica no banco


def test_serialize_usuario_created_at_iso_quando_preenchido():
    u = Usuario(nome="A", email="a@t.com", role="admin", senha_hash="h")
    u.created_at = datetime(2025, 6, 1, 12, 0, 0)
    result = serialize_usuario(u)
    assert result["created_at"] == "2025-06-01T12:00:00"


# ── serialize_imovel ──────────────────────────────────────────────────────────────


def test_serialize_imovel_sem_endereco_nao_inclui_chave():
    im = Imovel(tipo="apartamento", status="disponivel", garagem=False, garagem_vagas=0)
    result = serialize_imovel(im)
    assert "endereco" not in result


def test_serialize_imovel_campos_basicos():
    im = Imovel(
        tipo="casa",
        codigo="C-001",
        titulo="Casa linda",
        tamanho="120m²",
        garagem=True,
        garagem_vagas=2,
        status="disponivel",
        observacoes="Boa localização",
    )
    result = serialize_imovel(im)
    assert result["tipo"] == "casa"
    assert result["codigo"] == "C-001"
    assert result["garagem"] is True
    assert result["garagem_vagas"] == 2


def test_serialize_imovel_com_endereco_none():
    im = SimpleNamespace(
        id="im-id",
        tipo="apt",
        codigo=None,
        titulo=None,
        tamanho=None,
        garagem=False,
        garagem_vagas=0,
        status="disponivel",
        observacoes=None,
        created_at=None,
        endereco=None,
    )
    result = serialize_imovel(im, include_endereco=True)
    assert "endereco" in result
    assert result["endereco"] is None


def test_serialize_imovel_com_endereco_preenchido():
    end = SimpleNamespace(
        rua="Rua X",
        numero="5",
        complemento=None,
        bairro="Bairro Y",
        cidade="Curitiba",
        estado="PR",
        cep="80000-000",
        latitude=-25.4,
        longitude=-49.2,
    )
    im = SimpleNamespace(
        id="im-id",
        tipo="apt",
        codigo=None,
        titulo=None,
        tamanho=None,
        garagem=False,
        garagem_vagas=0,
        status="disponivel",
        observacoes=None,
        created_at=None,
        endereco=end,
    )
    result = serialize_imovel(im, include_endereco=True)
    assert result["endereco"]["cidade"] == "Curitiba"
    assert result["endereco"]["estado"] == "PR"


# ── serialize_contrato ────────────────────────────────────────────────────────────


def test_serialize_contrato_datas_como_iso():
    ct = SimpleNamespace(
        id="ct-id",
        imovel_id="im-id",
        locatario_id="loc-id",
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 12, 31),
        valor_mensal=None,
        status="ativo",
        created_at=None,
    )
    result = serialize_contrato(ct)
    assert result["data_inicio"] == "2025-01-01"
    assert result["data_fim"] == "2025-12-31"


def test_serialize_contrato_valor_mensal_decimal_para_float():
    ct = SimpleNamespace(
        id="ct-id",
        imovel_id="im-id",
        locatario_id="loc-id",
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 12, 31),
        valor_mensal=Decimal("1500.50"),
        status="ativo",
        created_at=None,
    )
    result = serialize_contrato(ct)
    assert isinstance(result["valor_mensal"], float)
    assert result["valor_mensal"] == pytest.approx(1500.50)


def test_serialize_contrato_valor_mensal_none():
    ct = SimpleNamespace(
        id="ct-id",
        imovel_id="im-id",
        locatario_id="loc-id",
        data_inicio=date(2025, 1, 1),
        data_fim=date(2025, 12, 31),
        valor_mensal=None,
        status="ativo",
        created_at=None,
    )
    result = serialize_contrato(ct)
    assert result["valor_mensal"] is None


# ── serialize_checklist ───────────────────────────────────────────────────────────


def _make_checklist(**kwargs):
    defaults = dict(
        id="ck-id",
        contrato_id="ct-id",
        vistoriador_id="vist-id",
        tipo="inicial",
        status="em_preenchimento",
        data_vistoria=date(2025, 6, 1),
        created_at=datetime(2025, 6, 1),
        itens=[],
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_serialize_checklist_campos_basicos():
    ck = _make_checklist()
    result = serialize_checklist(ck)
    assert result["id"] == "ck-id"
    assert result["tipo"] == "inicial"
    assert result["status"] == "em_preenchimento"
    assert result["data_vistoria"] == "2025-06-01"


def test_serialize_checklist_sem_itens_nao_inclui_chave():
    ck = _make_checklist()
    result = serialize_checklist(ck, include_itens=False)
    assert "itens" not in result


def test_serialize_checklist_com_itens():
    item = SimpleNamespace(
        id="i1",
        checklist_id="ck-id",
        comodo_id="cm-id",
        item_vistoria_id="iv-id",
        estado="otimo",
        observacao=None,
        fotos=[],
    )
    ck = _make_checklist(itens=[item])
    result = serialize_checklist(ck, include_itens=True)
    assert "itens" in result
    assert len(result["itens"]) == 1
    assert result["itens"][0]["estado"] == "otimo"


def test_serialize_checklist_sem_comodos_nao_inclui_chave():
    ck = _make_checklist()
    result = serialize_checklist(ck, comodos=None)
    assert "comodos" not in result


def test_serialize_checklist_com_comodos():
    comodo = ImovelComodo(id="cm-id", imovel_id="im-id", tipo="sala", nome="Sala")
    ck = _make_checklist()
    result = serialize_checklist(ck, comodos=[comodo])
    assert "comodos" in result
    assert len(result["comodos"]) == 1
    assert result["comodos"][0]["tipo"] == "sala"


def test_serialize_checklist_data_vistoria_none():
    ck = _make_checklist(data_vistoria=None)
    result = serialize_checklist(ck)
    assert result["data_vistoria"] is None


# ── paginate [requer db] ──────────────────────────────────────────────────────────


def test_paginate_primeira_pagina(db):
    for i in range(5):
        db.add(ItemVistoria(nome=f"Item {i}", categoria="Teste"))
    db.flush()

    items, pag = paginate(db.query(ItemVistoria), pagina=1, por_pagina=3)

    assert len(items) == 3
    assert pag["total"] == 5
    assert pag["pagina"] == 1
    assert pag["itensPorPagina"] == 3


def test_paginate_segunda_pagina(db):
    for i in range(5):
        db.add(ItemVistoria(nome=f"Item {i}", categoria="Teste"))
    db.flush()

    items, pag = paginate(db.query(ItemVistoria), pagina=2, por_pagina=3)

    assert len(items) == 2  # 5 itens, página 2 com 3 por página → 2 restantes
    assert pag["total"] == 5


def test_paginate_alem_do_total_retorna_vazio(db):
    db.add(ItemVistoria(nome="Único", categoria="Teste"))
    db.flush()

    items, pag = paginate(db.query(ItemVistoria), pagina=99, por_pagina=20)

    assert items == []
    assert pag["total"] == 1  # total não é afetado pela página


def test_paginate_sem_registros(db):
    items, pag = paginate(db.query(ItemVistoria), pagina=1, por_pagina=20)

    assert items == []
    assert pag["total"] == 0


# ── log_operacao [requer db] ──────────────────────────────────────────────────────


def test_log_operacao_cria_registro(db, user_admin):
    log_operacao(db, user_admin.id, "create", "imovel", "im-id", "detalhe")

    row = db.query(LogOperacao).filter(LogOperacao.acao == "create").first()
    assert row is not None
    assert row.usuario_id == user_admin.id
    assert row.entidade == "imovel"
    assert row.entidade_id == "im-id"
    assert row.detalhes == "detalhe"


def test_log_operacao_sem_usuario(db):
    log_operacao(db, None, "sistema", "config")

    row = db.query(LogOperacao).filter(LogOperacao.acao == "sistema").first()
    assert row is not None
    assert row.usuario_id is None


def test_log_operacao_campos_opcionais_none(db, user_admin):
    log_operacao(db, user_admin.id, "logout")

    row = db.query(LogOperacao).filter(LogOperacao.acao == "logout").first()
    assert row.entidade is None
    assert row.entidade_id is None
    assert row.detalhes is None


# ── ensure_default_comodos [requer db] ────────────────────────────────────────────


def test_ensure_default_comodos_cria_4_comodos(db):
    im = Imovel(tipo="casa", status="disponivel", garagem=False, garagem_vagas=0)
    db.add(im)
    db.flush()

    ensure_default_comodos(db, im.id)

    comodos = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == im.id).all()
    assert len(comodos) == 4
    nomes = {c.nome for c in comodos}
    assert nomes == {"Sala", "Cozinha", "Quarto 1", "Banheiro"}


def test_ensure_default_comodos_idempotente(db):
    im = Imovel(tipo="casa", status="disponivel", garagem=False, garagem_vagas=0)
    db.add(im)
    db.flush()

    ensure_default_comodos(db, im.id)
    ensure_default_comodos(db, im.id)  # segunda chamada não deve duplicar

    comodos = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == im.id).all()
    assert len(comodos) == 4


def test_ensure_default_comodos_nao_cria_se_ja_existem(db, imovel):
    # fixture imovel já criou 4 cômodos
    count_antes = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).count()
    ensure_default_comodos(db, imovel.id)
    count_depois = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).count()
    assert count_antes == count_depois


# ── get_comodos_for_checklist [requer db] ─────────────────────────────────────────


def test_get_comodos_for_checklist_retorna_comodos(db, checklist):
    # checklist → contrato → imovel com 4 cômodos (via fixture)
    comodos = get_comodos_for_checklist(db, checklist)
    assert len(comodos) == 4


def test_get_comodos_for_checklist_contrato_inexistente(db):
    ck = SimpleNamespace(contrato_id="id-que-nao-existe")
    comodos = get_comodos_for_checklist(db, ck)
    assert comodos == []


def test_get_comodos_for_checklist_ordenados_por_tipo(db, checklist):
    comodos = get_comodos_for_checklist(db, checklist)
    tipos = [c.tipo for c in comodos]
    assert tipos == sorted(tipos)


# ── serialize_aceite / atualizacao / problema ─────────────────────────────────────


def test_serialize_aceite_none():
    from app.serializers import serialize_aceite

    assert serialize_aceite(None) is None


def test_serialize_aceite_campos():
    from app.serializers import serialize_aceite

    a = SimpleNamespace(
        id="ac-1",
        checklist_id="ck-1",
        locatario_id="u-1",
        status="rejeitado",
        motivo_rejeicao="Itens danificados",
        created_at=datetime(2026, 1, 1, 10, 0, 0),
    )
    res = serialize_aceite(a)
    assert res["id"] == "ac-1"
    assert res["status"] == "rejeitado"
    assert res["motivo_rejeicao"] == "Itens danificados"
    assert res["created_at"] == "2026-01-01T10:00:00"


def test_serialize_atualizacao_problema_campos():
    from app.serializers import serialize_atualizacao_problema

    at = SimpleNamespace(
        id="at-1",
        problema_id="pb-1",
        autor_id="u-1",
        descricao="Equipe enviada",
        foto_url="foto.png",
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    res = serialize_atualizacao_problema(at)
    assert res["id"] == "at-1"
    assert res["descricao"] == "Equipe enviada"
    assert res["foto_url"] == "foto.png"


def test_serialize_problema_com_atualizacoes():
    from app.serializers import serialize_problema

    at = SimpleNamespace(
        id="at-1",
        problema_id="pb-1",
        autor_id="u-1",
        descricao="Equipe enviada",
        foto_url=None,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    pb = SimpleNamespace(
        id="pb-1",
        contrato_id="ct-1",
        comodo_id="cm-1",
        titulo="Infiltração",
        descricao="Teto úmido",
        foto_url="/uploads/teto.jpg",
        prioridade="alta",
        status="em_andamento",
        created_at=datetime(2026, 1, 1, 8, 0, 0),
        atualizacoes=[at],
    )
    res = serialize_problema(pb)
    assert res["id"] == "pb-1"
    assert res["comodo_id"] == "cm-1"
    assert res["foto_url"] == "/uploads/teto.jpg"
    assert len(res["atualizacoes"]) == 1
    assert res["atualizacoes"][0]["id"] == "at-1"
