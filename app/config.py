import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Render Postgres usa postgres:// — SQLAlchemy 2.x exige postgresql://
_db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'onecheck.db'}")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url

# Secure by default: sem APP_ENV, vale a regra de produção
APP_ENV = os.getenv("APP_ENV", "").strip().lower() or "production"
IS_DEV = APP_ENV in ("development", "dev", "local", "test")

MIN_SECRET_LEN = 32
# Valores que já estiveram no repositório (fallback antigo e exemplo do README): são públicos
_PUBLIC_JWT_SECRETS = {"onecheck-dev-secret-change-me", "sua_chave_secreta_jwt_super_segura"}


def _jwt_secret() -> str:
    valor = os.getenv("JWT_SECRET", "").strip()
    publico = not valor or valor in _PUBLIC_JWT_SECRETS
    if IS_DEV:
        if publico:
            # Tokens deixam de valer a cada reinício; serve só para desenvolvimento
            logging.getLogger(__name__).warning("JWT_SECRET ausente ou público: usando valor aleatório (APP_ENV=%s)", APP_ENV)
            return secrets.token_urlsafe(48)
        return valor
    if publico or len(valor) < MIN_SECRET_LEN:
        raise RuntimeError(
            f"JWT_SECRET ausente, público ou com menos de {MIN_SECRET_LEN} caracteres. "
            "Gere um com: python -c \"import secrets; print(secrets.token_urlsafe(48))\" "
            "(ou use APP_ENV=development localmente)."
        )
    return valor


JWT_SECRET = _jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_MINUTES", "60"))
JWT_REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "30"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

# Sem SEED_SECRET (ou com o antigo valor padrão, que é público) as rotas /admin/* ficam desabilitadas
_PUBLIC_SEED_SECRETS = {"onecheck-seed-dev"}
_seed_secret = os.getenv("SEED_SECRET", "").strip()
SEED_SECRET = "" if _seed_secret in _PUBLIC_SEED_SECRETS else _seed_secret
if SEED_SECRET and not IS_DEV and len(SEED_SECRET) < MIN_SECRET_LEN:
    raise RuntimeError(f"SEED_SECRET precisa ter pelo menos {MIN_SECRET_LEN} caracteres (ou ficar vazio para desabilitar /admin/*).")

# force=true e refresh_data apagam dados: só com opt-in explícito
SEED_ALLOW_DESTRUCTIVE = os.getenv("SEED_ALLOW_DESTRUCTIVE", "false").strip().lower() in ("1", "true", "yes")

_cors = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = ["*"] if _cors.strip() == "*" else [o.strip() for o in _cors.split(",") if o.strip()]

# Limite de tentativas falhas (login, MFA, reautenticação) por conta e por IP, numa janela deslizante
RATE_LIMIT_FALHAS_CONTA = int(os.getenv("RATE_LIMIT_FALHAS_CONTA", "5"))
RATE_LIMIT_FALHAS_IP = int(os.getenv("RATE_LIMIT_FALHAS_IP", "20"))
RATE_LIMIT_JANELA_MIN = int(os.getenv("RATE_LIMIT_JANELA_MIN", "15"))
