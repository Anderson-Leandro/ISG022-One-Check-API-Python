from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_token, sessao_vigente
from app.database import get_db
from app.models import Checklist, Contrato, Usuario

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
    if not sessao_vigente(payload, user):
        raise HTTPException(status_code=401, detail="Sessão encerrada; faça login novamente")
    return user


def require_roles(*roles: str):
    def _dep(user: Usuario = Depends(get_current_user)) -> Usuario:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(status_code=403, detail="Permissão negada")
        return user

    return _dep


def _vistoriador_atua_no_contrato(db: Session, contrato_id: str, user: Usuario) -> bool:
    return db.query(Checklist.id).filter(
        Checklist.contrato_id == contrato_id, Checklist.vistoriador_id == user.id
    ).first() is not None


def assert_acesso_contrato(db: Session, contrato: Contrato, user: Usuario) -> None:
    """Mesma regra da listagem de contratos: locatário só os próprios, vistoriador só onde tem vistoria."""
    if user.role == "locatario" and contrato.locatario_id != user.id:
        raise HTTPException(status_code=403, detail="Você não tem acesso a este contrato")
    if user.role == "vistoriador" and not _vistoriador_atua_no_contrato(db, contrato.id, user):
        raise HTTPException(status_code=403, detail="Você não tem acesso a este contrato")


def assert_acesso_imovel(db: Session, imovel_id: str, user: Usuario) -> None:
    """Mesma regra da listagem de imóveis: locatário com contrato ativo, vistoriador com vistoria no imóvel."""
    if user.role == "locatario":
        permitido = db.query(Contrato.id).filter(
            Contrato.imovel_id == imovel_id, Contrato.locatario_id == user.id, Contrato.status == "ativo"
        ).first()
    elif user.role == "vistoriador":
        permitido = (
            db.query(Checklist.id)
            .join(Contrato, Contrato.id == Checklist.contrato_id)
            .filter(Contrato.imovel_id == imovel_id, Checklist.vistoriador_id == user.id)
            .first()
        )
    else:
        return
    if not permitido:
        raise HTTPException(status_code=403, detail="Você não tem acesso a este imóvel")


def assert_acesso_problemas(contrato: Contrato, user: Usuario) -> None:
    """Regra única para listar, registrar e ler problemas de um contrato: admin, gestor ou o locatário dono."""
    if user.role in ("admin", "gestor"):
        return
    if user.role == "locatario" and contrato.locatario_id == user.id:
        return
    raise HTTPException(status_code=403, detail="Você não tem acesso aos problemas deste contrato")
