"""
Segurança — SEC-014 e SEC-015: CPF e retenção de dados, MFA configurado por terceiros

Cenários originais:
  - SEC-014: o CPF ia completo em toda resposta de usuário (inclusive na listagem),
    sem validação de formato, e log_operacao e os refresh tokens vencidos nunca
    eram apagados.
  - SEC-015: POST /usuarios/{id}/mfa/setup devolvia o segredo TOTP ao admin, e
    .../mfa/enable gravava um segredo escolhido por ele: o admin passava a gerar
    os códigos do usuário.

Regras verificadas:
  - o CPF completo só aparece para o próprio usuário e no detalhe para admin/gestor;
    nas demais respostas vai mascarado
  - CPF inválido é recusado; o válido é gravado no formato 000.000.000-00
  - a limpeza apaga refresh tokens vencidos e logs mais antigos que a retenção
  - o admin só exige ou reseta o MFA; o segredo é gerado no login do próprio usuário
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyotp
import pytest

from app.cpf import mascarar_cpf, validar_cpf
from app.models import LogOperacao, RefreshToken, Usuario
from app.retencao import limpar_dados_vencidos
from tests.conftest import MFA_TEST_SECRET, TEST_SENHA, _SENHA_HASH, auth

RAIZ = Path(__file__).resolve().parents[2]
USUARIOS = "/api/v1/usuarios"
CPF = "529.982.247-25"
MASCARADO = "***.982.247-**"


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── SEC-014: validação e máscara ─────────────────────────────────────────────────

class TestCpf:
    @pytest.mark.parametrize("valor", [CPF, "52998224725", " 529.982.247-25 "])
    def test_normaliza(self, valor):
        assert validar_cpf(valor) == CPF

    @pytest.mark.parametrize("valor", ["529.982.247-26", "000.000.000-00", "111.111.111-11", "1234", "abc.def.ghi-jk"])
    def test_recusa_invalido(self, valor):
        with pytest.raises(ValueError):
            validar_cpf(valor)

    @pytest.mark.parametrize("valor", [None, "", "   "])
    def test_vazio_vira_none(self, valor):
        assert validar_cpf(valor) is None

    def test_mascara(self):
        assert mascarar_cpf(CPF) == MASCARADO
        assert mascarar_cpf("52998224725") == MASCARADO

    def test_mascara_valor_antigo_fora_do_formato(self):
        assert mascarar_cpf("123") == "***.***.***-**"
        assert mascarar_cpf(None) is None


@pytest.fixture
def com_cpf(db, user_locatario):
    user_locatario.cpf = CPF
    db.commit()
    return user_locatario


class TestCpfNasRespostas:
    def test_proprio_usuario_ve_completo(self, client, com_cpf, token_locatario):
        assert client.get(f"{USUARIOS}/me", headers=auth(token_locatario)).json()["dados"]["cpf"] == CPF

    def test_detalhe_para_admin_completo(self, client, com_cpf, token_admin):
        r = client.get(f"{USUARIOS}/{com_cpf.id}", headers=auth(token_admin))
        assert r.json()["dados"]["cpf"] == CPF

    def test_listagem_mascarada(self, client, com_cpf, token_gestor):
        dados = client.get(USUARIOS, headers=auth(token_gestor)).json()["dados"]
        assert [u["cpf"] for u in dados if u["id"] == com_cpf.id] == [MASCARADO]

    def test_edicao_pelo_admin_mascarada(self, client, com_cpf, token_admin):
        r = client.put(f"{USUARIOS}/{com_cpf.id}", json={"nome": "Outro"}, headers=auth(token_admin))
        assert r.json()["dados"]["cpf"] == MASCARADO

    def test_criacao_valida_e_mascara(self, client, db, token_admin):
        body = {"nome": "N", "email": "n@test.com", "senha": "Vistoria-Casa-42", "role": "locatario",
                "cpf": "52998224725"}
        r = client.post(USUARIOS, json=body, headers=auth(token_admin))
        assert r.json()["dados"]["cpf"] == MASCARADO
        assert db.query(Usuario).filter(Usuario.email == "n@test.com").one().cpf == CPF

    def test_criacao_recusa_cpf_invalido(self, client, db, token_admin):
        body = {"nome": "N", "email": "n@test.com", "senha": "Vistoria-Casa-42", "role": "locatario",
                "cpf": "111.111.111-11"}
        r = client.post(USUARIOS, json=body, headers=auth(token_admin))
        assert r.status_code == 422
        assert db.query(Usuario).filter(Usuario.email == "n@test.com").count() == 0


# ── SEC-014: retenção ────────────────────────────────────────────────────────────

class TestRetencao:
    def _token(self, db, usuario, expira):
        db.add(RefreshToken(usuario_id=usuario.id, token_hash=f"h-{expira.isoformat()}", expires_at=expira))

    def _log(self, db, criado):
        db.add(LogOperacao(acao="login", entidade="usuario", ip="10.0.0.1", created_at=criado))

    def test_apaga_tokens_vencidos(self, db, user_locatario):
        self._token(db, user_locatario, _agora() - timedelta(minutes=1))
        self._token(db, user_locatario, _agora() + timedelta(days=1))
        db.commit()
        assert limpar_dados_vencidos(db)["refresh_tokens"] == 1
        assert db.query(RefreshToken).count() == 1

    def test_apaga_logs_alem_da_retencao(self, db, monkeypatch):
        import app.retencao as retencao
        monkeypatch.setattr(retencao, "LOG_RETENCAO_DIAS", 200)
        self._log(db, _agora() - timedelta(days=201))
        self._log(db, _agora() - timedelta(days=199))
        db.commit()
        assert limpar_dados_vencidos(db)["logs"] == 1
        assert db.query(LogOperacao).count() == 1

    def test_script_de_limpeza(self, db, user_locatario, capsys):
        import importlib.util
        spec = importlib.util.spec_from_file_location("limpeza", RAIZ / "scripts" / "limpar_dados_vencidos.py")
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)

        self._token(db, user_locatario, _agora() - timedelta(minutes=1))
        db.commit()
        assert script.main() == 0
        db.expire_all()
        assert db.query(RefreshToken).count() == 0
        assert "1 refresh token" in capsys.readouterr().out

    def test_retencao_minima_de_seis_meses(self, monkeypatch):
        import importlib
        import app.config as config
        monkeypatch.setenv("LOG_RETENCAO_DIAS", "30")
        with pytest.raises(RuntimeError, match="180"):
            importlib.reload(config)
        monkeypatch.delenv("LOG_RETENCAO_DIAS")
        importlib.reload(config)


# ── SEC-015: MFA de outro usuário ────────────────────────────────────────────────

class TestMfaPorTerceiros:
    def test_setup_de_outro_usuario_nao_existe(self, client, user_vistoriador, token_admin):
        r = client.post(f"{USUARIOS}/{user_vistoriador.id}/mfa/setup", headers=auth(token_admin))
        assert r.status_code in (404, 405)
        assert "secret" not in r.text

    @pytest.mark.parametrize("sufixo", ["/mfa/enable", "/mfa/habilitar"])
    def test_admin_nao_define_o_segredo(self, client, db, user_locatario, token_admin, sufixo):
        segredo = pyotp.random_base32()
        r = client.post(f"{USUARIOS}/{user_locatario.id}{sufixo}",
                        json={"secret": segredo, "codigo": pyotp.TOTP(segredo).now()}, headers=auth(token_admin))
        assert r.status_code == 422 and "secret" in r.json()["erros"]
        db.expire_all()
        assert db.get(Usuario, user_locatario.id).mfa_secret is None

    def test_admin_exige_mfa_e_o_usuario_configura_no_login(self, client, db, token_admin):
        # Vistoriador sem autenticador: o próximo login pede a configuração, com segredo gerado no servidor
        vist = Usuario(nome="V", email="v2@test.com", senha_hash=_SENHA_HASH, role="vistoriador",
                       mfa_enabled=False, ativo=True)
        db.add(vist)
        db.commit()
        r = client.post(f"{USUARIOS}/{vist.id}/mfa/enable", headers=auth(token_admin))
        assert r.json()["sucesso"] is True and r.json()["dados"]["mfa_enabled"] is True
        assert r.json()["dados"]["mfa_configurado"] is False
        login = client.post("/api/v1/auth/login", json={"email": vist.email, "senha": TEST_SENHA}).json()["dados"]
        assert login["mfa_setup_required"] is True

    def test_habilitar_nao_troca_autenticador_existente(self, client, db, user_vistoriador, token_admin):
        client.post(f"{USUARIOS}/{user_vistoriador.id}/mfa/habilitar", headers=auth(token_admin))
        db.expire_all()
        assert db.get(Usuario, user_vistoriador.id).mfa_secret == MFA_TEST_SECRET

    def test_reset_continua_disponivel(self, client, db, user_vistoriador, token_admin):
        r = client.delete(f"{USUARIOS}/{user_vistoriador.id}/mfa", headers=auth(token_admin))
        assert r.json()["dados"]["mfa_configurado"] is False
