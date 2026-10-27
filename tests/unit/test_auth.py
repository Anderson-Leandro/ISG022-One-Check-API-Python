"""
Fase 1.1 — Testes unitários de app/auth.py

Grupos:
  - Hash de senha
  - Tokens de acesso (JWT)
  - Token MFA temporário
  - Refresh token  [requer db]
  - MFA / TOTP
  - usuario_to_dict
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
import pytest

from app.auth import (
    _hash_refresh,
    create_access_token,
    create_refresh_token,
    create_temp_token,
    decode_token,
    generate_mfa_secret,
    hash_password,
    mfa_provisioning_data,
    mfa_setup_required,
    needs_mfa,
    revoke_refresh_token,
    usuario_to_dict,
    verify_password,
    verify_refresh_token,
    verify_totp,
    verify_totp_code,
)
from app.config import JWT_ALGORITHM, JWT_SECRET
from app.models import RefreshToken, Usuario

MFA_TEST_SECRET = "JBSWY3DPEHPK3PXP"


# ── Hash de senha ────────────────────────────────────────────────────────────────

def test_hash_password_returns_bcrypt_string():
    h = hash_password("qualquersenha")
    assert h.startswith("$2b$")


def test_verify_password_correct():
    h = hash_password("senha123")
    assert verify_password("senha123", h) is True


def test_verify_password_wrong():
    h = hash_password("senha123")
    assert verify_password("errada", h) is False


def test_verify_password_invalid_hash():
    # Não deve levantar exceção — deve retornar False
    assert verify_password("senha", "hash-invalido-qualquer") is False


# ── Tokens de acesso ─────────────────────────────────────────────────────────────

def test_create_access_token_decodable():
    token = create_access_token("user-id-123", "admin")
    payload = decode_token(token)
    assert payload is not None


def test_access_token_contains_correct_fields():
    token = create_access_token("user-id-456", "gestor")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-456"
    assert payload["role"] == "gestor"
    assert payload["type"] == "access"


def test_decode_token_invalid_signature():
    token = jwt.encode(
        {
            "sub": "x",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "chave-errada-com-32-caracteres-ou-mais",
        algorithm=JWT_ALGORITHM,
    )
    assert decode_token(token) is None


def test_decode_token_expired():
    token = jwt.encode(
        {
            "sub": "x",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    assert decode_token(token) is None


def test_decode_token_malformed_string():
    assert decode_token("nao.e.um.jwt") is None


def test_decode_token_empty_string():
    assert decode_token("") is None


# ── Token MFA temporário ─────────────────────────────────────────────────────────

def test_create_temp_token_type_is_mfa():
    token = create_temp_token("user-id-789")
    payload = decode_token(token)
    assert payload is not None
    assert payload["type"] == "mfa"
    assert payload["sub"] == "user-id-789"


def test_temp_token_expires_in_10_minutes():
    agora = datetime.now(timezone.utc)
    token = create_temp_token("user-id-abc")
    payload = decode_token(token)
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    diferenca_segundos = (exp - agora).total_seconds()
    # 10 minutos com tolerância de ±5 segundos
    assert 595 <= diferenca_segundos <= 605


# ── Refresh token [requer db] ─────────────────────────────────────────────────────

def test_create_refresh_token_persists_hash(db, user_locatario):
    raw = create_refresh_token(db, user_locatario.id)
    assert raw  # token raw não é vazio

    esperado = hashlib.sha256(raw.encode()).hexdigest()
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == esperado).first()
    assert row is not None
    assert row.usuario_id == user_locatario.id


def test_verify_refresh_token_valid(db, user_locatario):
    raw = create_refresh_token(db, user_locatario.id)
    user = verify_refresh_token(db, raw)
    assert user is not None
    assert user.id == user_locatario.id


def test_verify_refresh_token_wrong_value(db):
    assert verify_refresh_token(db, "valor-que-nao-existe") is None


def test_verify_refresh_token_expired(db, user_locatario):
    raw = create_refresh_token(db, user_locatario.id)
    # Forçar expiração no passado
    h = _hash_refresh(raw)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == h).first()
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    db.flush()
    assert verify_refresh_token(db, raw) is None


def test_verify_refresh_token_inactive_user(db, user_locatario):
    raw = create_refresh_token(db, user_locatario.id)
    user_locatario.ativo = False
    db.flush()
    assert verify_refresh_token(db, raw) is None


def test_revoke_refresh_token_removes_record(db, user_locatario):
    raw = create_refresh_token(db, user_locatario.id)
    revoke_refresh_token(db, raw)
    h = _hash_refresh(raw)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == h).first()
    assert row is None


# ── MFA / TOTP ───────────────────────────────────────────────────────────────────

def test_verify_totp_code_valid():
    codigo = pyotp.TOTP(MFA_TEST_SECRET).now()
    assert verify_totp_code(MFA_TEST_SECRET, codigo) is True


def test_verify_totp_code_invalid():
    totp = pyotp.TOTP(MFA_TEST_SECRET)
    if totp.verify("000000", valid_window=1):
        pytest.skip("000000 é código TOTP válido neste instante — reexecute o teste")
    assert verify_totp_code(MFA_TEST_SECRET, "000000") is False


def test_verify_totp_code_strips_whitespace():
    codigo = pyotp.TOTP(MFA_TEST_SECRET).now()
    assert verify_totp_code(MFA_TEST_SECRET, f"  {codigo}  ") is True


def test_verify_totp_no_secret(user_locatario):
    user_locatario.mfa_secret = None
    assert verify_totp(user_locatario, "123456") is False


def test_verify_totp_with_valid_code(user_admin):
    # user_admin já tem MFA_TEST_SECRET configurado via conftest
    codigo = pyotp.TOTP(MFA_TEST_SECRET).now()
    assert verify_totp(user_admin, codigo) is True


def test_generate_mfa_secret_is_base32():
    secret = generate_mfa_secret()
    assert secret  # não vazio
    # Deve ser decodificável como base32 — levanta exceção se inválido
    base64.b32decode(secret)


def test_generate_mfa_secret_is_unique():
    assert generate_mfa_secret() != generate_mfa_secret()


def test_needs_mfa_true(user_admin):
    # admin com mfa_enabled=True e mfa_secret definido
    assert needs_mfa(user_admin) is True


def test_needs_mfa_false_sem_secret(user_admin):
    user_admin.mfa_secret = None
    assert needs_mfa(user_admin) is False


def test_needs_mfa_false_mfa_disabled(user_admin):
    user_admin.mfa_enabled = False
    assert needs_mfa(user_admin) is False


def test_needs_mfa_false_role_nao_obrigatorio(user_locatario):
    # locatario não está em MFA_REQUIRED_ROLES
    user_locatario.mfa_enabled = True
    user_locatario.mfa_secret = MFA_TEST_SECRET
    assert needs_mfa(user_locatario) is False


def test_mfa_setup_required_true():
    u = Usuario(role="admin", mfa_enabled=True, mfa_secret=None)
    assert mfa_setup_required(u) is True


def test_mfa_setup_required_false_com_secret():
    u = Usuario(role="admin", mfa_enabled=True, mfa_secret=MFA_TEST_SECRET)
    assert mfa_setup_required(u) is False


def test_mfa_setup_required_false_role_nao_obrigatorio():
    u = Usuario(role="locatario", mfa_enabled=True, mfa_secret=None)
    assert mfa_setup_required(u) is False


def test_mfa_provisioning_data_tem_chaves():
    dados = mfa_provisioning_data("usuario@test.com", MFA_TEST_SECRET)
    assert "secret" in dados
    assert "provisioning_uri" in dados
    assert "qr_url" in dados


def test_mfa_provisioning_data_secret_correto():
    dados = mfa_provisioning_data("usuario@test.com", MFA_TEST_SECRET)
    assert dados["secret"] == MFA_TEST_SECRET


def test_mfa_provisioning_data_uri_contem_issuer():
    dados = mfa_provisioning_data("usuario@test.com", MFA_TEST_SECRET)
    assert "OneCheck" in dados["provisioning_uri"]


def test_mfa_provisioning_data_uri_contem_email():
    dados = mfa_provisioning_data("usuario@test.com", MFA_TEST_SECRET)
    assert "usuario" in dados["provisioning_uri"]


# ── usuario_to_dict ──────────────────────────────────────────────────────────────

def test_usuario_to_dict_campos(user_admin):
    d = usuario_to_dict(user_admin)
    assert d["id"] == user_admin.id
    assert d["nome"] == user_admin.nome
    assert d["email"] == user_admin.email
    assert d["role"] == user_admin.role


def test_usuario_to_dict_sem_campos_sensiveis(user_admin):
    d = usuario_to_dict(user_admin)
    assert "senha_hash" not in d
    assert "mfa_secret" not in d
