import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import SEED_ALLOW_DESTRUCTIVE, SEED_SECRET
from app.data_status import get_data_status
from app.database import get_db
from app.deps import get_current_user, security
from app.models import Usuario
from app.schemas import fail, ok
from app.seed_service import run_expand, run_refresh_data, run_seed

router = APIRouter(prefix="/admin", tags=["admin"])


class SeedRequest(BaseModel):
    force: bool = False
    mode: str = Field(default="full", description="full | expand | refresh_data")


def require_seed_access(
    x_seed_secret: str | None = Header(default=None, alias="X-Seed-Secret"),
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario | None:
    """
    Exige o X-Seed-Secret e, se o banco já tiver usuários, também um admin autenticado.
    Banco vazio (primeiro deploy) aceita só o segredo. Retorna o admin ou None no bootstrap.
    """
    if not SEED_SECRET:
        raise HTTPException(status_code=404, detail="Not Found")
    if not x_seed_secret or not hmac.compare_digest(x_seed_secret.encode(), SEED_SECRET.encode()):
        raise HTTPException(status_code=403, detail="Seed secret inválido")

    if db.query(Usuario.id).first() is None:
        return None

    user = get_current_user(creds, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Permissão negada")
    return user


def _require_destructive_allowed() -> None:
    if not SEED_ALLOW_DESTRUCTIVE:
        raise HTTPException(
            status_code=403,
            detail="Operação destrutiva desabilitada (defina SEED_ALLOW_DESTRUCTIVE=true)",
        )


def _refresh_data(db: Session) -> dict:
    result = run_refresh_data(db)
    if not result.get("seeded"):
        return fail(result["message"])
    result["preservado"] = "usuarios"
    return ok(result)


@router.get("/data/status")
def data_status(
    _: Usuario | None = Depends(require_seed_access),
    db: Session = Depends(get_db),
):
    """Retorna totais do banco sem alterar dados."""
    return ok(get_data_status(db))


@router.post("/refresh-data")
@router.put("/refresh-data")
@router.patch("/refresh-data")
def refresh_data(
    _: Usuario | None = Depends(require_seed_access),
    db: Session = Depends(get_db),
):
    """
    Recria imóveis (com lat/lng), contratos, vistorias, problemas e catálogo.
    **Não altera usuários** (senhas, MFA e perfis permanecem).
    """
    _require_destructive_allowed()
    return _refresh_data(db)


@router.post("/seed")
def seed_database(
    body: SeedRequest | None = None,
    _: Usuario | None = Depends(require_seed_access),
    db: Session = Depends(get_db),
):
    body = body or SeedRequest()
    if body.force or body.mode == "refresh_data":
        _require_destructive_allowed()

    if body.mode == "expand":
        result = run_expand(db)
    elif body.mode == "refresh_data":
        result = run_refresh_data(db)
    else:
        result = run_seed(db, force=body.force)

    if not result.get("seeded"):
        return fail(result["message"])

    if body.mode == "refresh_data":
        result["preservado"] = "usuarios"
    return ok(result)
