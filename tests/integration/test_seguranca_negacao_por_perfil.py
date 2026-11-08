"""
Segurança — DEBT-011: negação por perfil em todas as rotas restritas (OWASP API5:2023, CWE-285)

A avaliação SPK-005 (docs/quality/avaliacao-testes-2026-11-02.md, seção 2) mostrou que 77 das 97
combinações "perfil proibido × rota com require_roles" nunca eram testadas. Uma rota que perdesse a
dependência numa refatoração não era detectada.

Duas camadas:
  1. ROTAS_RESTRITAS é a lista esperada, escrita à mão. test_lista_confere_com_a_api compara com as
     rotas que de fato usam require_roles: rota nova, perfil a mais ou dependência removida quebram
     o teste, e quem mudar precisa atualizar a lista de propósito.
  2. test_perfil_proibido_recebe_403 chama cada rota com cada perfil fora da lista, usando IDs de
     objetos reais, e confere 403 e o banco igual ao de antes.
"""
import pytest
from fastapi.routing import APIRoute

from app.database import Base
from app.models import AgendamentoVistoria, Endereco, ImovelComodo, LogOperacao, Problema
from app.routers import (
    admin,
    agendamentos,
    auth_router,
    checklists,
    contratos,
    dashboard,
    health,
    imoveis,
    problemas,
    usuarios,
)
from tests.conftest import auth

API = "/api/v1"
PERFIS = ("admin", "gestor", "vistoriador", "locatario")
ADMIN_GESTOR = ("admin", "gestor")

# (método, rota, perfis permitidos). O admin passa em toda require_roles (app/deps.py).
ROTAS_RESTRITAS = [
    ("POST", "/auth/mfa/disable", ("admin",)),
    ("GET", "/usuarios", ADMIN_GESTOR),
    ("POST", "/usuarios", ADMIN_GESTOR),
    ("GET", "/usuarios/{usuario_id}", ADMIN_GESTOR),
    ("PUT", "/usuarios/{usuario_id}", ADMIN_GESTOR),
    ("DELETE", "/usuarios/{usuario_id}", ADMIN_GESTOR),
    ("POST", "/usuarios/{usuario_id}/mfa/habilitar", ADMIN_GESTOR),
    ("POST", "/usuarios/{usuario_id}/mfa/enable", ADMIN_GESTOR),
    ("POST", "/usuarios/{usuario_id}/mfa/desabilitar", ADMIN_GESTOR),
    ("DELETE", "/usuarios/{usuario_id}/mfa", ADMIN_GESTOR),
    ("POST", "/imoveis", ADMIN_GESTOR),
    ("PUT", "/imoveis/{imovel_id}", ADMIN_GESTOR),
    ("DELETE", "/imoveis/{imovel_id}", ADMIN_GESTOR),
    ("POST", "/imoveis/{imovel_id}/endereco", ADMIN_GESTOR),
    ("PUT", "/imoveis/{imovel_id}/endereco", ADMIN_GESTOR),
    ("PATCH", "/imoveis/{imovel_id}/endereco", ADMIN_GESTOR),
    ("POST", "/imoveis/{imovel_id}/comodos", ADMIN_GESTOR),
    ("PUT", "/imoveis/{imovel_id}/comodos/{comodo_id}", ADMIN_GESTOR),
    ("DELETE", "/imoveis/{imovel_id}/comodos/{comodo_id}", ADMIN_GESTOR),
    ("POST", "/contratos", ADMIN_GESTOR),
    ("DELETE", "/contratos/{contrato_id}", ADMIN_GESTOR),
    ("POST", "/contratos/{contrato_id}/encerrar", ADMIN_GESTOR),
    ("PATCH", "/contratos/{contrato_id}/encerrar", ADMIN_GESTOR),
    ("POST", "/contratos/{contrato_id}/cancelar", ADMIN_GESTOR),
    ("PATCH", "/contratos/{contrato_id}/cancelar", ADMIN_GESTOR),
    ("POST", "/contratos/{contrato_id}/agendamentos", ADMIN_GESTOR),
    ("POST", "/contratos/{contrato_id}/checklists", ADMIN_GESTOR),
    ("PUT", "/agendamentos/{agendamento_id}", ADMIN_GESTOR),
    ("DELETE", "/agendamentos/{agendamento_id}", ADMIN_GESTOR),
    ("DELETE", "/checklists/{checklist_id}", ADMIN_GESTOR),
    ("PATCH", "/checklists/{checklist_id}/enviar-para-aceite", ADMIN_GESTOR),
    ("DELETE", "/problemas/{problema_id}", ADMIN_GESTOR),
    ("POST", "/problemas/{problema_id}/atualizacoes", ("admin", "gestor", "locatario")),
    ("PATCH", "/problemas/{problema_id}/status", ADMIN_GESTOR),
    ("GET", "/logs", ("admin",)),
]

COMBINACOES_PROIBIDAS = [
    pytest.param(metodo, rota, perfil, id=f"{metodo} {rota} [{perfil}]")
    for metodo, rota, permitidos in ROTAS_RESTRITAS
    for perfil in PERFIS
    if perfil not in permitidos
]


def _perfis_da_dependencia(rota: APIRoute) -> set[str] | None:
    """Perfis passados a require_roles nas dependências da rota (None se a rota não usa)."""
    achados = []

    def visitar(dependant):
        for dep in dependant.dependencies:
            if getattr(dep.call, "__qualname__", "").startswith("require_roles."):
                achados.append(set(dep.call.__closure__[0].cell_contents))
            visitar(dep)

    visitar(rota.dependant)
    return set.union(*achados) if achados else None


def _rotas_da_api():
    for modulo in (health, auth_router, usuarios, imoveis, contratos, agendamentos, checklists, problemas,
                   dashboard, admin):
        for rota in modulo.router.routes:
            if isinstance(rota, APIRoute):
                yield rota


# ── 1. A lista esperada confere com a API ───────────────────────────────────────

def test_lista_confere_com_a_api(client):
    na_api = set()
    for rota in _rotas_da_api():
        perfis = _perfis_da_dependencia(rota)
        if perfis is not None:
            for metodo in rota.methods:
                na_api.add((metodo, rota.path, tuple(sorted(perfis | {"admin"}))))
    esperado = {(m, r, tuple(sorted(p))) for m, r, p in ROTAS_RESTRITAS}

    assert na_api == esperado, (
        f"faltam na lista: {sorted(na_api - esperado)}; não estão mais na API: {sorted(esperado - na_api)}"
    )
    # Os caminhos montados aqui são os mesmos que a API publica
    publicados = client.app.openapi()["paths"]
    assert all(f"{API}{r}" in publicados for _, r, _ in ROTAS_RESTRITAS)


def test_combinacoes_cobertas():
    """32 rotas de admin e gestor × vistoriador e locatário, as 2 rotas só de admin (MFA disable e, desde o
    SEC-018, GET /logs) × 3 perfis e POST /problemas/{id}/atualizacoes, que desde o US-019 aceita também o
    locatário (só o vistoriador é proibido).

    Eram 97 na avaliação SPK-005 e 106 com o US-015; as 35 do visualizador saíram com o perfil (ADR-0009).
    """
    assert len(COMBINACOES_PROIBIDAS) == 32 * 2 + 2 * 3 + 1


# ── 2. Cada perfil proibido recebe 403 e nada é gravado ─────────────────────────

@pytest.fixture
def ids(db, imovel, contrato, checklist, user_locatario):
    comodo = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()
    agendamento = db.query(AgendamentoVistoria).filter(AgendamentoVistoria.contrato_id == contrato.id).first()
    problema = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(problema)
    db.add(Endereco(imovel_id=imovel.id, rua="Rua A", cidade="Cidade", estado="SP", ativo=True))
    db.flush()
    return {
        "usuario_id": user_locatario.id,
        "imovel_id": imovel.id,
        "comodo_id": comodo.id,
        "contrato_id": contrato.id,
        "agendamento_id": agendamento.id,
        "checklist_id": checklist.id,
        "problema_id": problema.id,
    }


@pytest.fixture
def tokens(token_admin, token_gestor, token_vistoriador, token_locatario):
    return {"admin": token_admin, "gestor": token_gestor, "vistoriador": token_vistoriador,
            "locatario": token_locatario}


def _foto_do_banco(db):
    db.expire_all()
    return {
        tabela.name: sorted(map(repr, db.execute(tabela.select()).all()))
        for tabela in Base.metadata.sorted_tables
    }


@pytest.mark.parametrize(("metodo", "rota", "perfil"), COMBINACOES_PROIBIDAS)
def test_perfil_proibido_recebe_403(client, db, ids, tokens, metodo, rota, perfil):
    antes = _foto_do_banco(db)
    kwargs = {"headers": auth(tokens[perfil])}
    if metodo in ("POST", "PUT", "PATCH"):
        kwargs["json"] = {}

    r = client.request(metodo, f"{API}{rota.format(**ids)}", **kwargs)

    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "Permissão negada"
    assert _foto_do_banco(db) == antes


# ── 3. Rotas que não tinham nenhum teste ────────────────────────────────────────

_ENDERECO = {"rua": "Rua Nova", "numero": "10", "cidade": "Campinas", "estado": "SP"}


def test_patch_endereco_pelo_gestor(client, db, ids, token_gestor):
    r = client.patch(f"{API}/imoveis/{ids['imovel_id']}/endereco", json=_ENDERECO, headers=auth(token_gestor))
    assert r.status_code == 200, r.text
    assert r.json()["dados"]["rua"] == "Rua Nova"
    db.expire_all()
    assert db.query(Endereco).filter(Endereco.imovel_id == ids["imovel_id"]).one().cidade == "Campinas"


@pytest.mark.parametrize(("acao", "status"), [("encerrar", "encerrado"), ("cancelar", "cancelado")])
def test_post_encerrar_e_cancelar_pelo_gestor(client, db, contrato, imovel, token_gestor, acao, status):
    r = client.post(f"{API}/contratos/{contrato.id}/{acao}", headers=auth(token_gestor))
    assert r.status_code == 200, r.text
    assert r.json()["dados"]["status"] == status
    db.expire_all()
    assert imovel.status == "disponivel"


def test_gestor_nao_le_os_logs(client, db, user_admin, token_gestor, token_admin):
    """SEC-018 (decisão do PO em 2026-11-08): a trilha de auditoria é só do admin."""
    db.add(LogOperacao(usuario_id=user_admin.id, acao="login", entidade="usuario", entidade_id=user_admin.id, ip="203.0.113.7"))
    db.flush()

    r = client.get(f"{API}/logs", headers=auth(token_gestor))

    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "Permissão negada"
    assert "203.0.113.7" not in r.text
    admin = client.get(f"{API}/logs", headers=auth(token_admin))
    assert admin.status_code == 200, admin.text
    assert [(log["acao"], log["ip"]) for log in admin.json()["dados"]] == [("login", "203.0.113.7")]
