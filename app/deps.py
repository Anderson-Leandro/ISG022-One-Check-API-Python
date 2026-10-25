from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import Contrato, Usuario

security = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Token ausente")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token inválido")
    user = db.query(Usuario).filter(Usuario.id == payload["sub"], Usuario.ativo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def require_roles(*roles: str):
    def _dep(user: Usuario = Depends(get_current_user)) -> Usuario:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(status_code=403, detail="Permissão negada")
        return user

    return _dep


def assert_acesso_problemas(contrato: Contrato, user: Usuario) -> None:
    """Regra única para listar, registrar e ler problemas de um contrato: admin, gestor ou o locatário dono."""
    if user.role in ("admin", "gestor"):
        return
    if user.role == "locatario" and contrato.locatario_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Você não tem acesso aos problemas deste contrato")
