from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import PRIVILEGED_ROLES, ROLES, decode_token, sessao_vigente
from app.database import get_db
from app.models import Checklist, Contrato, Usuario

security = HTTPBearer(auto_error=False)


SENHA_EXPIRADA = "Sua senha não atende à política atual: troque-a em PUT /api/v1/usuarios/me/senha"


def usuario_mesmo_com_senha_expirada(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario:
    """O usuário do token, mesmo com senha_expirada (SEC-029). Só para ver o próprio perfil, trocar a senha e sair."""
    return usuario_autenticado(creds, db)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> Usuario:
    """O usuário do token. Com senha_expirada, 403: até trocar a senha, as outras rotas ficam fechadas (SEC-029)."""
    return exigir_senha_em_dia(usuario_autenticado(creds, db))


def exigir_senha_em_dia(user: Usuario) -> Usuario:
    if user.senha_expirada:
        raise HTTPException(status_code=403, detail=SENHA_EXPIRADA)
    return user


def usuario_autenticado(creds: HTTPAuthorizationCredentials | None, db: Session) -> Usuario:
    """O usuário do token de acesso, sem a restrição da senha expirada (a rota do seed usa só esta parte)."""
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
    # Fail secure (ADR-0009): as regras de acesso restringem só locatário e vistoriador; um perfil fora da
    # lista (removido, digitado errado, gravado por script) seria tratado como admin/gestor
    if user.role not in ROLES:
        raise HTTPException(status_code=401, detail="Perfil de acesso inválido")
    return user


def require_roles(*roles: str):
    def _dep(user: Usuario = Depends(get_current_user)) -> Usuario:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(status_code=403, detail="Permissão negada")
        return user

    return _dep


def _vistoriador_atua_no_contrato(db: Session, contrato_id: str, user: Usuario) -> bool:
    return (
        db.query(Checklist.id).filter(Checklist.contrato_id == contrato_id, Checklist.vistoriador_id == user.id).first()
        is not None
    )


# Perfis com visão de toda a operação: a mesma lista de app.auth (PRIVILEGED_ROLES). Toda regra de acesso libera
# estes explicitamente e nega qualquer perfil fora de ROLES (DEBT-017): um perfil desconhecido nunca cai no
# acesso total
PERFIS_GESTAO = PRIVILEGED_ROLES


def negar_perfil_desconhecido(user: Usuario) -> None:
    """Fail secure: recusa perfil que nenhuma regra conhece, mesmo num caminho que não passe pelo get_current_user.

    Chamar antes de buscar o registro: assim um perfil desconhecido não distingue, pelo 404 contra 403, quais
    IDs existem.
    """
    if user.role not in ROLES:
        raise HTTPException(status_code=403, detail="Permissão negada")


def assert_acesso_contrato(db: Session, contrato: Contrato, user: Usuario) -> None:
    """Mesma regra da listagem de contratos: locatário só os próprios, vistoriador só onde tem vistoria."""
    negar_perfil_desconhecido(user)
    if user.role == "locatario" and contrato.locatario_id != user.id:
        raise HTTPException(status_code=403, detail="Você não tem acesso a este contrato")
    if user.role == "vistoriador" and not _vistoriador_atua_no_contrato(db, contrato.id, user):
        raise HTTPException(status_code=403, detail="Você não tem acesso a este contrato")


def assert_acesso_imovel(db: Session, imovel_id: str, user: Usuario) -> None:
    """Mesma regra da listagem de imóveis: locatário com contrato ativo, vistoriador com vistoria no imóvel."""
    negar_perfil_desconhecido(user)
    if user.role == "locatario":
        permitido = (
            db.query(Contrato.id)
            .filter(Contrato.imovel_id == imovel_id, Contrato.locatario_id == user.id, Contrato.status == "ativo")
            .first()
        )
    elif user.role == "vistoriador":
        permitido = (
            db.query(Checklist.id)
            .join(Contrato, Contrato.id == Checklist.contrato_id)
            .filter(Contrato.imovel_id == imovel_id, Checklist.vistoriador_id == user.id)
            .first()
        )
    else:  # PERFIS_GESTAO
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
