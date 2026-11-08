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
