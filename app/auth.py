import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pyotp
from sqlalchemy.orm import Session

from app.config import (
    JWT_ACCESS_MINUTES,
    JWT_ALGORITHM,
    JWT_REFRESH_DAYS,
    JWT_SECRET,
)
from app.models import RefreshToken, Usuario

ROLES = {"admin", "gestor", "vistoriador", "locatario", "visualizador"}
# Só admin atribui estes perfis ou gerencia contas que os possuem
PRIVILEGED_ROLES = {"admin", "gestor"}
MFA_REQUIRED_ROLES = {"admin", "vistoriador", "gestor"}


def hash_password(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verify_password(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), senha_hash.encode())
    except ValueError:
        return False


# Mesmo custo de hash_password: conferir contra ele leva o mesmo tempo que contra uma conta real
_HASH_FICTICIO = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode()


def conferir_credenciais(user: Usuario | None, senha: str) -> bool:
    """Confere a senha gastando o mesmo tempo quando a conta não existe, para não revelar quais e-mails existem."""
    senha_ok = verify_password(senha, user.senha_hash if user else _HASH_FICTICIO)
    return user is not None and senha_ok


def create_access_token(usuario_id: str, role: str, versao: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_ACCESS_MINUTES)
    payload = {"sub": usuario_id, "role": role, "type": "access", "ver": versao, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _create_short_token(usuario_id: str, token_type: str, versao: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {"sub": usuario_id, "type": token_type, "ver": versao, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_temp_token(usuario_id: str, versao: int = 0) -> str:
    """Token do passo de verificação MFA (usuário já tem autenticador)."""
    return _create_short_token(usuario_id, "mfa", versao)


def create_mfa_setup_token(usuario_id: str, versao: int = 0) -> str:
    """Token do primeiro acesso, para configurar o autenticador. Não serve para /mfa/verify."""
    return _create_short_token(usuario_id, "mfa_setup", versao)


def sessao_vigente(payload: dict, user: Usuario) -> bool:
    """O token foi emitido depois da última troca de credencial do usuário."""
    return payload.get("ver", 0) == (user.token_version or 0)


def encerrar_sessoes(db: Session, user: Usuario) -> None:
    """Invalida todas as sessões do usuário: access tokens pela versão e refresh tokens apagados. Não faz commit."""
    user.token_version = (user.token_version or 0) + 1
    db.query(RefreshToken).filter(RefreshToken.usuario_id == user.id).delete()


def nova_sessao(db: Session, user: Usuario) -> dict:
    """Tokens novos para quem acabou de trocar a própria credencial (as outras sessões foram encerradas)."""
    return {
        "access_token": create_access_token(user.id, user.role, user.token_version),
        "refresh_token": create_refresh_token(db, user.id),
    }


def decode_token(token: str) -> dict | None:
    try:
        # algorithms fixo impede alg=none e troca de algoritmo; sem exp/sub/type, o token é recusado
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub", "type"]})
    except jwt.InvalidTokenError:
        return None


def _hash_refresh(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_refresh_token(db: Session, usuario_id: str) -> str:
    raw = secrets.token_urlsafe(48)
    token = RefreshToken(
        usuario_id=usuario_id,
        token_hash=_hash_refresh(raw),
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=JWT_REFRESH_DAYS),
    )
    db.add(token)
    db.commit()
    return raw


def verify_refresh_token(db: Session, raw: str) -> Usuario | None:
    h = _hash_refresh(raw)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == h).first()
    if not row or row.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        return None
    return db.query(Usuario).filter(Usuario.id == row.usuario_id, Usuario.ativo).first()


def revoke_refresh_token(db: Session, raw: str) -> None:
    h = _hash_refresh(raw)
    db.query(RefreshToken).filter(RefreshToken.token_hash == h).delete()
    db.commit()


def needs_mfa(user: Usuario) -> bool:
    return (
        user.role in MFA_REQUIRED_ROLES and user.mfa_enabled and bool(user.mfa_secret)
    )


def mfa_setup_required(user: Usuario) -> bool:
    return user.role in MFA_REQUIRED_ROLES and user.mfa_enabled and not user.mfa_secret


def reset_mfa(user: Usuario) -> None:
    """Remove o autenticador. Em perfis obrigatórios o MFA continua exigido e o próximo login pede nova configuração."""
    user.mfa_secret = None
    user.mfa_secret_pendente = None
    user.mfa_enabled = user.role in MFA_REQUIRED_ROLES


def verify_totp_code(secret: str, codigo: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(codigo.strip(), valid_window=1)


def verify_totp(user: Usuario, codigo: str) -> bool:
    if not user.mfa_secret:
        return False
    return verify_totp_code(user.mfa_secret, codigo)


def mfa_self_disable_error(user: Usuario, senha: str, codigo: str | None) -> str | None:
    """Reautenticação para o usuário desligar o próprio MFA: senha e, se houver autenticador, código atual."""
    if not verify_password(senha, user.senha_hash):
        return "Senha incorreta"
    if user.mfa_secret and not (codigo and verify_totp(user, codigo)):
        return "Código MFA inválido"
    return None


def mfa_troca_error(user: Usuario, codigo_atual: str | None) -> str | None:
    """Trocar um autenticador em uso exige provar posse dele com o código TOTP atual."""
    if user.mfa_enabled and user.mfa_secret and not (codigo_atual and verify_totp(user, codigo_atual)):
        return "Código do autenticador atual inválido"
    return None


def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def mfa_provisioning_data(email: str, secret: str) -> dict:
    import urllib.parse

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=email, issuer_name="OneCheck")
    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data="
        + urllib.parse.quote(uri, safe="")
    )
    return {
        "secret": secret,
        "provisioning_uri": uri,
        "otpauth_uri": uri,
        "qr_url": qr_url,
    }


def usuario_to_dict(user: Usuario) -> dict:
    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "role": user.role,
    }
