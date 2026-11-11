"""
DEBT-002 — O envelope e os campos das rotas principais no OpenAPI

As rotas principais declaram, em `responses`, o envelope {sucesso, dados, paginacao} com o modelo de
`dados`, e os envelopes de erro {sucesso, erro, erros}. Aqui cada rota é chamada de verdade e a
resposta é validada contra o modelo declarado, que recusa campo a mais: se um serializador ganhar ou
perder um campo, este teste avisa que a documentação ficou para trás.
"""

import pytest
from pydantic import TypeAdapter

from app.models import AtualizacaoProblema, Problema
from app.respostas import Envelope, ErroResposta, UsuarioResposta
from tests.conftest import TEST_SENHA, auth, totp_now

API = "/api/v1"


@pytest.fixture
def problema(db, contrato, user_admin):
    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.flush()
    db.add(AtualizacaoProblema(problema_id=pb.id, autor_id=user_admin.id, descricao="Visita marcada"))
    db.flush()
    return pb


@pytest.fixture
def openapi(client):
    return client.get("/openapi.json").json()


def _modelo_declarado(openapi, caminho, metodo, status):
    """O nome do schema que a rota declara para o status (o envelope gerado pelo FastAPI)."""
    conteudo = openapi["paths"][API + caminho][metodo]["responses"][str(status)]["content"]["application/json"]
    return conteudo["schema"]["$ref"].rsplit("/", 1)[-1]


def _modelo_python(nome):
    """Envelope[...] gerado a partir do nome do schema, para validar a resposta real."""
    from app import respostas

    interno = nome.removeprefix("Envelope_").removesuffix("_")
    if interno.startswith("list_"):
        return Envelope[list[getattr(respostas, interno.removeprefix("list_").removesuffix("_"))]]
    return Envelope[getattr(respostas, interno)]


def _confere(client, openapi, metodo, caminho, rota, status=200, **kwargs):
    r = client.request(metodo, API + rota, **kwargs)
    assert r.status_code == status, r.text
    nome = _modelo_declarado(openapi, caminho, metodo.lower(), status)
    TypeAdapter(_modelo_python(nome)).validate_python(r.json())
    return r.json()


def test_usuarios(client, openapi, user_locatario, token_admin, token_locatario):
    _confere(client, openapi, "GET", "/usuarios/me", "/usuarios/me", headers=auth(token_locatario))
    lista = _confere(client, openapi, "GET", "/usuarios", "/usuarios", headers=auth(token_admin))
    assert lista["paginacao"] is not None
    _confere(
        client, openapi, "GET", "/usuarios/{usuario_id}", f"/usuarios/{user_locatario.id}", headers=auth(token_admin)
    )
    corpo = {"nome": "N", "email": "n@test.com", "senha": "Vistoria-Casa-42", "role": "locatario"}
    _confere(client, openapi, "POST", "/usuarios", "/usuarios", headers=auth(token_admin), json=corpo)


def test_imoveis(client, openapi, imovel, token_admin):
    _confere(client, openapi, "GET", "/imoveis", "/imoveis", headers=auth(token_admin))
    _confere(client, openapi, "GET", "/imoveis/{imovel_id}", f"/imoveis/{imovel.id}", headers=auth(token_admin))
    _confere(
        client,
        openapi,
        "GET",
        "/imoveis/{imovel_id}/comodos",
        f"/imoveis/{imovel.id}/comodos",
        headers=auth(token_admin),
    )


def test_contratos_e_filhos(client, openapi, contrato, checklist, problema, token_admin, token_locatario):
    h = auth(token_admin)
    _confere(client, openapi, "GET", "/contratos", "/contratos", headers=h)
    _confere(client, openapi, "GET", "/contratos/{contrato_id}", f"/contratos/{contrato.id}", headers=h)
    agendamentos = "/contratos/{contrato_id}/agendamentos"
    _confere(client, openapi, "GET", agendamentos, f"/contratos/{contrato.id}/agendamentos", headers=h)
    # O locatário recebe o agendamento sem a observação: o modelo também aceita essa forma
    _confere(
        client, openapi, "GET", agendamentos, f"/contratos/{contrato.id}/agendamentos", headers=auth(token_locatario)
    )
    _confere(
        client, openapi, "GET", "/contratos/{contrato_id}/checklists", f"/contratos/{contrato.id}/checklists", headers=h
    )
    _confere(
        client, openapi, "GET", "/contratos/{contrato_id}/problemas", f"/contratos/{contrato.id}/problemas", headers=h
    )
    _confere(client, openapi, "GET", "/checklists/{checklist_id}", f"/checklists/{checklist.id}", headers=h)
    _confere(client, openapi, "GET", "/problemas/{problema_id}", f"/problemas/{problema.id}", headers=h)
    _confere(
        client,
        openapi,
        "POST",
        "/contratos/{contrato_id}/problemas",
        f"/contratos/{contrato.id}/problemas",
        status=201,
        headers=h,
        json={"titulo": "Vazamento"},
    )


def test_login_e_refresh(client, openapi, user_locatario):
    login = _confere(
        client, openapi, "POST", "/auth/login", "/auth/login", json={"email": user_locatario.email, "senha": TEST_SENHA}
    )
    refresh = login["dados"]["refresh_token"]
    _confere(client, openapi, "POST", "/auth/refresh", "/auth/refresh", json={"refresh_token": refresh})


def test_login_com_mfa_tem_a_outra_forma(client, openapi, user_admin):
    dados = _confere(
        client, openapi, "POST", "/auth/login", "/auth/login", json={"email": user_admin.email, "senha": TEST_SENHA}
    )["dados"]
    assert dados["mfa_required"] is True and "access_token" not in dados


@pytest.mark.parametrize(
    "metodo,rota,status,formato",
    [
        ("GET", "/contratos/00000000-0000-0000-0000-000000000000", 404, ErroResposta),
        ("POST", "/auth/login", 401, ErroResposta),  # credenciais inválidas
        ("GET", "/usuarios/me", 401, ErroResposta),  # sem token
        ("POST", "/auth/login", 422, ErroResposta),  # corpo fora do schema
    ],
)
def test_erros_seguem_um_dos_formatos_documentados(client, token_admin, metodo, rota, status, formato):
    headers = auth(token_admin) if status == 404 else {}
    corpo = {"email": "ninguem@exemplo.com", "senha": "x"} if status == 401 and metodo == "POST" else {}
    r = client.request(metodo, API + rota, headers=headers, json=corpo if metodo == "POST" else None)
    assert r.status_code == status
    formato.model_validate(r.json())


def test_formatos_de_erro_estao_nos_componentes(openapi):
    assert "ErroResposta" in openapi["components"]["schemas"]
    erro_401 = openapi["paths"][API + "/usuarios/me"]["get"]["responses"]["401"]["content"]["application/json"]
    assert erro_401["schema"]["$ref"].rsplit("/", 1)[-1] == "ErroResposta"


def test_rotas_principais_declaram_envelope_e_erros(openapi):
    declaradas = [
        (c, m, op)
        for c, ops in openapi["paths"].items()
        for m, op in ops.items()
        if any(str(cod).startswith("2") and "Envelope" in str(v) for cod, v in op.get("responses", {}).items())
    ]
    assert len(declaradas) >= 18
    for caminho, metodo, op in declaradas:
        erros = [v for cod, v in op["responses"].items() if str(cod)[0] in "45"]
        # Todo erro, inclusive o 422 que o próprio FastAPI acrescenta, é o envelope (DEBT-020)
        assert erros and all("ErroResposta" in str(v) for v in erros), (caminho, metodo)


def test_campos_do_mfa_explicados_no_schema(openapi):
    props = openapi["components"]["schemas"]["UsuarioResposta"]["properties"]
    assert {"mfa_enabled", "mfa_configurado", "mfa_ativo", "role"} <= set(props)
    for campo in ("mfa_enabled", "mfa_configurado", "mfa_ativo", "role"):
        assert props[campo].get("description"), campo
    assert set(UsuarioResposta.model_fields) == set(props)


def test_criacoes(client, openapi, contrato, user_locatario_2, user_vistoriador, token_admin, monkeypatch):
    from app.routers import imoveis as rota_imoveis

    # A criação com endereço consulta o geocoding: sem rede nos testes
    monkeypatch.setattr(rota_imoveis, "buscar_coordenadas", lambda *a, **k: None)
    h = auth(token_admin)
    endereco = {"rua": "Rua A", "numero": "10", "cidade": "Recife", "estado": "PE"}
    imovel = _confere(
        client, openapi, "POST", "/imoveis", "/imoveis", headers=h, json={"tipo": "casa", "endereco": endereco}
    )
    novo = {
        "imovel_id": imovel["dados"]["id"],
        "locatario_id": user_locatario_2.id,
        "data_inicio": "2026-01-01",
        "data_fim": "2026-12-31",
    }
    _confere(client, openapi, "POST", "/contratos", "/contratos", headers=h, json=novo)
    _confere(
        client,
        openapi,
        "POST",
        "/contratos/{contrato_id}/checklists",
        f"/contratos/{contrato.id}/checklists",
        headers=h,
        json={"tipo": "encerramento", "vistoriador_id": user_vistoriador.id},
    )


def test_login_mfa_verify_e_primeiro_acesso(client, openapi, db, user_admin, user_locatario):
    temp = _confere(
        client, openapi, "POST", "/auth/login", "/auth/login", json={"email": user_admin.email, "senha": TEST_SENHA}
    )
    corpo = {"temp_token": temp["dados"]["temp_token"], "codigo": totp_now()}
    _confere(client, openapi, "POST", "/auth/mfa/verify", "/auth/mfa/verify", json=corpo)

    user_locatario.mfa_enabled = True  # MFA ligado e sem autenticador: o login leva à configuração
    db.commit()
    login = {"email": user_locatario.email, "senha": TEST_SENHA}
    dados = _confere(client, openapi, "POST", "/auth/login", "/auth/login", json=login)["dados"]
    assert dados["mfa_setup_required"] is True


def test_sucesso_e_obrigatorio_e_erros_sem_ref_ao_lado_do_anyof(openapi):
    schemas = openapi["components"]["schemas"]
    assert "sucesso" in schemas["ErroResposta"]["required"]
    envelopes = [n for n in schemas if n.startswith("Envelope_")]
    assert envelopes and all("sucesso" in schemas[n]["required"] for n in envelopes)
    for ops in openapi["paths"].values():
        for op in ops.values():
            for codigo, resposta in op.get("responses", {}).items():
                schema = resposta.get("content", {}).get("application/json", {}).get("schema", {})
                if "anyOf" in schema:
                    assert "$ref" not in schema, codigo


def test_criacao_de_problema_documenta_so_o_201(openapi):
    respostas = openapi["paths"][API + "/contratos/{contrato_id}/problemas"]["post"]["responses"]
    assert "201" in respostas and "200" not in respostas


def test_cada_rota_lista_os_proprios_erros(openapi):
    me = openapi["paths"][API + "/usuarios/me"]["get"]["responses"]
    assert "404" not in me and "401" in me
    login = openapi["paths"][API + "/auth/login"]["post"]["responses"]
    assert {"401", "422", "429"} <= set(login)
    criar_contrato = openapi["paths"][API + "/contratos"]["post"]["responses"]
    assert {"400", "409"} <= set(criar_contrato)
