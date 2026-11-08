"""Testes do scripts/dod_check.py (a partir do TK-019): as conferências feitas só sobre o texto do registro."""
import importlib.util
from pathlib import Path

import pytest

_ARQ = Path(__file__).resolve().parents[2] / "scripts" / "dod_check.py"
_spec = importlib.util.spec_from_file_location("dod_check", _ARQ)
dod_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dod_check)

MODELO = (Path(__file__).resolve().parents[2] / "docs/roadmap/execucao/_modelo.md").read_text(encoding="utf-8")


class TestChecklistAntesDaRevisao:
    def test_registro_antigo_sem_a_secao_nao_e_cobrado(self):
        assert dod_check.checklist_pendente("## Entrega\nfeito\n## Testes\nok\n") is None

    def test_modelo_em_branco_tem_as_cinco_linhas_pendentes(self):
        assert len(dod_check.checklist_pendente(MODELO)) == 5

    def test_linha_sem_resposta_e_apontada(self):
        registro = ("## Checklist antes da revisão\n- [x] Campos: só tipo e data\n"
                    "- [ ] Status finais: todos tratados\n- [-] Login: não se aplica, sem sessão\n## Testes\n")
        pendentes = dod_check.checklist_pendente(registro)
        assert len(pendentes) == 1 and pendentes[0].startswith("Status finais")

    @pytest.mark.parametrize("linha", ["* [ ] Campos", "-[ ] Campos", "- [  ] Campos", "1. [ ] Campos"])
    def test_outras_grafias_de_caixa_vazia_sao_pendentes(self, linha):
        assert dod_check.checklist_pendente(f"## Checklist antes da revisão\n{linha}\n## Testes\n") == ["Campos"]

    def test_secao_sem_linhas_conta_como_pendente(self):
        assert dod_check.checklist_pendente("## Checklist antes da revisão\n<!-- nada -->\n## Testes\n")

    def test_titulo_citado_no_meio_do_texto_nao_conta(self):
        registro = ("## Entrega\nAdiciona `## Checklist antes da revisão` ao modelo.\n"
                    "## Checklist antes da revisão\n- [ ] Status finais\n## Testes\n")
        assert dod_check.checklist_pendente(registro) == ["Status finais"]

    def test_tudo_respondido_passa(self):
        registro = "## Checklist antes da revisão\n- [x] a\n- [-] b\n## Testes\n"
        assert dod_check.checklist_pendente(registro) == []

    @pytest.mark.parametrize("item", ["Campos que o perfil", "Status finais", "Autorização antes de ler o corpo",
                                      "Login, refresh e tokens", "Perfis proibidos barrados antes da busca"])
    def test_modelo_traz_cada_item_da_checklist(self, item):
        assert item in MODELO.split("## Checklist antes da revisão", 1)[1].split("\n## ", 1)[0]


# DEBT-018: falsos negativos do dod_check
def _pr(base, arquivos=(), estado="MERGED", ci="SUCCESS", branch="dev"):
    return {"number": 172, "state": estado, "baseRefName": base, "headRefName": branch, "mergeCommit": None,
            "statusCheckRollup": [{"name": "test", "conclusion": ci}], "files": [{"path": a} for a in arquivos]}


class TestPrDeRelease:
    @pytest.fixture
    def conferir(self, monkeypatch):
        def _conferir(pr, iid="DEBT-007"):
            monkeypatch.setattr(dod_check, "resultados", [])
            monkeypatch.setattr(dod_check, "gh_json", lambda *a: pr)
            monkeypatch.setattr(dod_check, "testes_alterados", lambda pr: [])
            dod_check.conferir_pr(iid, "172", "", depois_do_merge=True)
            return dod_check.resultados
        return _conferir

    def test_release_na_main_nao_passa_pelas_checagens_de_implementacao(self, conferir):
        """Base main, branch 'dev' sem o ID e app/ sem tests/: nada disso é cobrado de uma release."""
        resultados = conferir(_pr("main", arquivos=["app/main.py"]))
        assert resultados == [(True, "PR #172: release na main mesclada com o CI verde")]

    @pytest.mark.parametrize("estado,ci", [("OPEN", "SUCCESS"), ("MERGED", "FAILURE")])
    def test_release_aberta_ou_com_ci_falho_reprova(self, conferir, estado, ci):
        assert [r for r, _ in conferir(_pr("main", estado=estado, ci=ci))] == [False]

    def test_feature_mesclada_direto_na_main_nao_vale_como_release(self, conferir):
        resultados = dict((m, r) for r, m in conferir(_pr("main", arquivos=["app/main.py"], branch="feat/x")))
        assert resultados["PR #172 mesclado na dev"] is False
        assert resultados["PR #172: muda app/ e traz testes"] is False

    def test_release_nao_conta_como_pr_de_implementacao(self, monkeypatch):
        monkeypatch.setattr(dod_check, "resultados", [])
        monkeypatch.setattr(dod_check, "testes_alterados", lambda pr: [])
        monkeypatch.setattr(dod_check, "gh_json", lambda *a: _pr("main"))
        assert dod_check.conferir_pr("DEBT-007", "172", "", True) is False
        monkeypatch.setattr(dod_check, "gh_json", lambda *a: _pr("dev", branch="chore/DEBT-007-x"))
        assert dod_check.conferir_pr("DEBT-007", "170", "", True) is True

    def test_pr_de_implementacao_continua_conferido(self, conferir):
        resultados = dict((m, r) for r, m in conferir(_pr("dev", arquivos=["app/main.py"], branch="feat/x")))
        assert resultados["PR #172: branch 'feat/x' leva o ID"] is False
        assert resultados["PR #172: muda app/ e traz testes"] is False


class TestIntervaloDeIds:
    @pytest.mark.parametrize("iid", ["SPK-001", "SPK-002", "SPK-004"])
    def test_intervalo_cita_cada_id(self, iid):
        assert dod_check.cita_id("| 08/11 | SPK-001 a SPK-004 concluídos |", iid)

    @pytest.mark.parametrize("texto", ["SPK-001 até SPK-004", "SPK-001–SPK-004", "SPK-001 - SPK-004"])
    def test_outras_grafias_de_intervalo(self, texto):
        assert dod_check.cita_id(texto, "SPK-003")

    def test_limites_com_larguras_diferentes_nao_contam(self):
        assert not dod_check.cita_id("SPK-001 a SPK-0040", "SPK-035")

    @pytest.mark.parametrize("iid", ["SPK-005", "SPK-000", "SEC-002", "SPK-01"])
    def test_fora_do_intervalo_ou_de_outro_tipo_nao_conta(self, iid):
        assert not dod_check.cita_id("SPK-001 a SPK-004", iid)

    def test_citacao_direta_exige_o_id_inteiro(self):
        assert dod_check.cita_id("DEBT-018 feito", "DEBT-018")
        assert not dod_check.cita_id("DEBT-0181 feito", "DEBT-018")
        assert not dod_check.cita_id("SEC-0350 feito", "SEC-035")


class TestRelatorioDeTestesAlterados:
    TODOS = ["tests/integration/test_auth.py", "tests/unit/test_auth.py", "tests/integration/test_problemas.py"]

    def test_nome_do_arquivo_unico_basta(self):
        assert dod_check.faltando_no_relatorio(
            ["tests/integration/test_problemas.py"], "| test_problemas.py :: test_x | ... |", self.TODOS) == []

    def test_nome_repetido_em_outra_pasta_exige_o_caminho(self):
        alterado = ["tests/unit/test_auth.py"]
        assert dod_check.faltando_no_relatorio(alterado, "| test_auth.py :: test_x |", self.TODOS) == alterado
        assert dod_check.faltando_no_relatorio(alterado, "| tests/unit/test_auth.py :: test_x |", self.TODOS) == []

    def test_caminho_completo_continua_valendo(self):
        alterado = ["tests/integration/test_problemas.py"]
        assert dod_check.faltando_no_relatorio(alterado, "tests/integration/test_problemas.py", self.TODOS) == []

    @pytest.mark.parametrize("citacao", ["old_test_problemas.py", "test_problemas.py.bak", "test_problemas.py-antigo"])
    def test_nome_com_prefixo_ou_sufixo_nao_conta(self, citacao):
        alterado = ["tests/integration/test_problemas.py"]
        assert dod_check.faltando_no_relatorio(alterado, f"| {citacao} :: test_x |", self.TODOS) == alterado

    def test_nome_parecido_nao_conta(self):
        alterado = ["tests/integration/test_problemas.py"]
        assert dod_check.faltando_no_relatorio(alterado, "old_test_problemas.py", self.TODOS) == alterado
        assert dod_check.faltando_no_relatorio(alterado, "nada citado", self.TODOS) == alterado


class TestSecaoSeguranca:
    @pytest.mark.parametrize("texto", [
        "- `/security-audit diff dev`: nenhum achado novo. Item SEC-019 continua pendente no backlog.",
        "- `/security-audit diff dev`: ok. Os itens pendentes ficam para a Sprint 14.",
        "- `/security-audit diff dev`: scanners ok; SEC-019 pendente.",
    ])
    def test_pendente_fora_da_auditoria_nao_reprova(self, texto):
        assert dod_check.auditoria_rodou(texto)

    @pytest.mark.parametrize("texto", [
        "- `/security-audit`: não foi rodada.",
        "- `/security-audit diff dev`: pendente.",
        "- A auditoria ficou pendente.",
        "- Nenhum scanner rodou.",
        "- Pendente: rodar a /security-audit antes do merge.",
        "- security-audit diff dev será rodada depois do review, resultado pendente.",
        "- `/security-audit`: não rodada (só docs).",
        "- security-audit ainda não executada.",
    ])
    def test_auditoria_nao_rodada_reprova(self, texto):
        assert not dod_check.auditoria_rodou(texto)

    def test_secao_le_so_o_titulo_no_comeco_da_linha(self):
        registro = "## Entrega\ncita ## Segurança no texto\n## Segurança\n- corpo\n## Documentação\n"
        assert dod_check.secao(registro, "Segurança").strip() == "- corpo"
        assert dod_check.secao(registro, "Inexistente") is None

    def test_titulo_com_complemento_conta_e_titulo_mais_longo_nao(self):
        registro = "## Testes existentes alterados (2)\n- a\n## Segurança: diff dev\n- b\n"
        assert dod_check.secao(registro, "Testes existentes alterados").strip() == "- a"
        assert dod_check.secao(registro, "Segurança").strip() == "- b"
        assert dod_check.secao(registro, "Testes") is None
