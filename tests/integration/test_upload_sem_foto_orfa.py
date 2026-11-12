"""
BUG-002 — Foto enviada fica órfã no disco quando o pedido é recusado depois do upload

Cenário original: em POST /contratos/{id}/problemas e POST /problemas/{id}/atualizacoes (multipart), a
foto era gravada em UPLOAD_DIR antes das validações seguintes. Se uma delas recusava o pedido (404, 409 ou
422), o arquivo ficava no disco sem nenhum registro apontando para ele; repetido, ocupava o disco.

Regras verificadas:
  - pedido recusado depois da foto (campo inválido, cômodo inexistente, status encerrado) não deixa arquivo
  - pedido aceito grava a foto e o registro aponta para ela
  - falha ao criar o registro (antes do commit) apaga a foto que acabou de ser gravada
  - foto do checklist: a nova sai se o registro falhar, e as antigas só saem do disco depois do commit
"""

import pytest

from app.config import UPLOAD_DIR
from app.models import AtualizacaoProblema, ChecklistItem, ChecklistItemFoto, ImovelComodo, Problema
from tests.conftest import auth, small_image_bytes

API = "/api/v1"


def _arquivos() -> set[str]:
    return {p.name for p in UPLOAD_DIR.glob("*")} if UPLOAD_DIR.exists() else set()


def _foto():
    return {"foto": ("a.png", small_image_bytes(), "image/png")}


def _falhar_ao_adicionar(monkeypatch, db, modelo):
    """O registro do modelo falha ao entrar na sessão: só acontece dentro do bloco que já gravou a foto."""
    original = db.add

    def add(obj, *a, **kw):
        if isinstance(obj, modelo):
            raise RuntimeError("banco fora do ar")
        return original(obj, *a, **kw)

    monkeypatch.setattr(db, "add", add)


@pytest.fixture
def problema(db, contrato):
    pb = Problema(contrato_id=contrato.id, titulo="Infiltração")
    db.add(pb)
    db.commit()
    return pb


class TestCriarProblema:
    @pytest.mark.parametrize(
        "campos,status",
        [
            ({"titulo": ""}, 422),
            ({"titulo": "Vazamento", "prioridade": "urgentissima"}, 422),
            ({"titulo": "Vazamento", "status": "resolvido"}, 422),
            ({"titulo": "Vazamento", "comodo_id": "00000000-0000-0000-0000-000000000000"}, 404),
        ],
    )
    def test_recusado_nao_deixa_arquivo(self, client, contrato, token_admin, campos, status):
        antes = _arquivos()
        r = client.post(
            f"{API}/contratos/{contrato.id}/problemas", data=campos, files=_foto(), headers=auth(token_admin)
        )
        assert r.status_code == status, r.text
        assert _arquivos() == antes

    def test_aceito_grava_e_aponta_para_a_foto(self, client, db, contrato, token_admin):
        antes = _arquivos()
        r = client.post(
            f"{API}/contratos/{contrato.id}/problemas",
            data={"titulo": "Vazamento"},
            files=_foto(),
            headers=auth(token_admin),
        )
        assert r.status_code == 201, r.text
        novos = _arquivos() - antes
        assert len(novos) == 1
        assert db.get(Problema, r.json()["dados"]["id"]).foto_url == novos.pop()

    def test_falha_ao_criar_o_registro_apaga_a_foto(self, client, db, contrato, token_admin, monkeypatch):
        antes = _arquivos()
        _falhar_ao_adicionar(monkeypatch, db, Problema)
        with pytest.raises(RuntimeError):
            client.post(
                f"{API}/contratos/{contrato.id}/problemas",
                data={"titulo": "Vazamento"},
                files=_foto(),
                headers=auth(token_admin),
            )
        assert _arquivos() == antes


class TestCriarAtualizacao:
    def test_descricao_curta_nao_deixa_arquivo(self, client, problema, token_admin):
        antes = _arquivos()
        r = client.post(
            f"{API}/problemas/{problema.id}/atualizacoes",
            data={"descricao": "ok"},
            files=_foto(),
            headers=auth(token_admin),
        )
        assert r.status_code == 422, r.text
        assert _arquivos() == antes

    def test_problema_encerrado_durante_o_upload_nao_deixa_arquivo(
        self, client, db, problema, token_locatario, monkeypatch
    ):
        # O status muda entre a leitura do formulário e a gravação: a segunda conferência recusa (409)
        original = db.refresh

        def refresh(obj, *a, **kw):
            original(obj, *a, **kw)
            if isinstance(obj, Problema):
                obj.status = "resolvido"

        monkeypatch.setattr(db, "refresh", refresh)
        antes = _arquivos()
        r = client.post(
            f"{API}/problemas/{problema.id}/atualizacoes",
            data={"descricao": "Continua pingando"},
            files=_foto(),
            headers=auth(token_locatario),
        )
        assert r.status_code == 409, r.text
        assert _arquivos() == antes
        # o status 'resolvido' foi só simulado: não pode ficar na sessão
        db.rollback()

    def test_aceito_grava_e_aponta_para_a_foto(self, client, db, problema, token_admin):
        antes = _arquivos()
        r = client.post(
            f"{API}/problemas/{problema.id}/atualizacoes",
            data={"descricao": "Visita marcada"},
            files=_foto(),
            headers=auth(token_admin),
        )
        assert r.status_code == 201, r.text
        novos = _arquivos() - antes
        assert len(novos) == 1
        assert db.query(AtualizacaoProblema).one().foto_url == novos.pop()


class TestFotoDoChecklist:
    @pytest.fixture
    def item(self, db, checklist, item_vistoria, imovel):
        comodo = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel.id).first()
        it = ChecklistItem(
            checklist_id=checklist.id, comodo_id=comodo.id, item_vistoria_id=item_vistoria.id, estado="bom"
        )
        db.add(it)
        db.commit()
        return it

    def _enviar(self, client, checklist, item, token):
        return client.post(f"{API}/checklists/{checklist.id}/itens/{item.id}/fotos", files=_foto(), headers=auth(token))

    def test_troca_apaga_a_antiga_depois_do_commit(self, client, db, checklist, item, token_vistoriador):
        primeira = self._enviar(client, checklist, item, token_vistoriador)
        assert primeira.status_code == 200, primeira.text
        antiga = db.query(ChecklistItemFoto).one().arquivo
        assert self._enviar(client, checklist, item, token_vistoriador).status_code == 200
        db.expire_all()
        nova = db.query(ChecklistItemFoto).one().arquivo
        assert antiga not in _arquivos() and nova in _arquivos()

    def test_falha_ao_criar_o_registro_mantem_a_antiga_e_apaga_a_nova(
        self, client, db, checklist, item, token_vistoriador, monkeypatch
    ):
        assert self._enviar(client, checklist, item, token_vistoriador).status_code == 200
        antes = _arquivos()
        _falhar_ao_adicionar(monkeypatch, db, ChecklistItemFoto)
        with pytest.raises(RuntimeError):
            self._enviar(client, checklist, item, token_vistoriador)
        assert _arquivos() == antes


class TestGravacaoInterrompida:
    def test_gravacao_que_falha_no_meio_nao_deixa_arquivo(self, monkeypatch):
        from pathlib import Path

        from app.uploads import gravar_imagem

        antes = _arquivos()

        def grava_metade(caminho, conteudo):
            caminho.open("wb").write(conteudo[:3])
            raise OSError("disco cheio")

        monkeypatch.setattr(Path, "write_bytes", grava_metade)
        with pytest.raises(OSError):
            gravar_imagem(small_image_bytes(), ".png")
        assert _arquivos() == antes
