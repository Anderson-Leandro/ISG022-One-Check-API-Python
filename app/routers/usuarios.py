from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import (
    MFA_REQUIRED_ROLES,
    PRIVILEGED_ROLES,
    ROLES,
    generate_mfa_secret,
    hash_password,
    mfa_provisioning_data,
    mfa_self_disable_error,
    mfa_troca_error,
    reset_mfa,
    verify_password,
    verify_totp_code,
)
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Usuario
from app.rate_limit import Tentativas
from app.schemas import (
    AlterarSenhaRequest,
    MfaDisableSelfRequest,
    MfaEnableRequest,
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioUpdateMe,
    fail,
    ok,
)
from app.serializers import log_operacao, paginate, serialize_usuario

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


def _assert_pode_gerenciar(current: Usuario, target: Usuario) -> None:
    """Rotas /usuarios/{id}: a própria conta só muda por /usuarios/me, e só admin gerencia admin/gestor."""
    if target.id == current.id:
        raise HTTPException(status_code=403, detail="Use /usuarios/me para alterar a própria conta")
    if target.role in PRIVILEGED_ROLES and current.role != "admin":
        raise HTTPException(status_code=403, detail="Permissão negada")


def _assert_pode_atribuir(current: Usuario, role: str) -> None:
    if role in PRIVILEGED_ROLES and current.role != "admin":
        raise HTTPException(status_code=403, detail="Só administradores atribuem este perfil")


@router.get("/me")
def me(user: Usuario = Depends(get_current_user)):
    return ok(serialize_usuario(user))


@router.patch("/me")
def update_me(
    body: UsuarioUpdateMe,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    if body.nome is not None:
        nome = body.nome.strip()
        if not nome:
            return fail("Nome é obrigatório")
        user.nome = nome

    if body.senha_nova:
        if not body.senha_atual:
            return fail("Informe a senha atual")
        tentativas = Tentativas(request, "reauth", user.id)
        tentativas.verificar()
        if not verify_password(body.senha_atual, user.senha_hash):
            tentativas.falhou()
            return fail("Senha atual incorreta")
        tentativas.sucesso()
        user.senha_hash = hash_password(body.senha_nova)

    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "perfil")
    return ok(serialize_usuario(user))


@router.put("/me/senha")
def alterar_senha_me(
    body: AlterarSenhaRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    tentativas = Tentativas(request, "reauth", user.id)
    tentativas.verificar()
    if not verify_password(body.senha_atual, user.senha_hash):
        tentativas.falhou()
        return fail("Senha atual incorreta")
    tentativas.sucesso()

    user.senha_hash = hash_password(body.nova_senha)
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "alteracao_de_senha")
    return ok({"mensagem": "Senha alterada com sucesso"})


@router.post("/me/mfa/setup")
def mfa_setup_me(user: Usuario = Depends(get_current_user)):
    secret = generate_mfa_secret()
    return ok(mfa_provisioning_data(user.email, secret))


@router.post("/me/mfa/enable")
def mfa_enable_me(
    body: MfaEnableRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    tentativas = Tentativas(request, "reauth", user.id)
    tentativas.verificar()
    erro = mfa_troca_error(user, body.codigo_atual)
    if erro:
        tentativas.falhou()
        return fail(erro)
    if not verify_totp_code(body.secret, body.codigo):
        return fail("Código MFA inválido")
    user.mfa_secret = body.secret
    user.mfa_enabled = True
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "mfa_enable")
    return ok(serialize_usuario(user))


@router.delete("/me/mfa")
def mfa_disable_me(
    body: MfaDisableSelfRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    if user.role in MFA_REQUIRED_ROLES:
        raise HTTPException(status_code=403, detail="MFA é obrigatório para este perfil")
    tentativas = Tentativas(request, "reauth", user.id)
    tentativas.verificar()
    erro = mfa_self_disable_error(user, body.senha, body.codigo)
    if erro:
        tentativas.falhou()
        return fail(erro)
    tentativas.sucesso()

    user.mfa_secret = None
    user.mfa_secret_pendente = None
    user.mfa_enabled = False
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "mfa_disable")
    return ok(serialize_usuario(user))


@router.get("")
def list_usuarios(
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(20, ge=1, le=100),
    role: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_roles("admin", "gestor")),
):
    q = db.query(Usuario).filter(Usuario.ativo == True)
    if role:
        q = q.filter(Usuario.role == role)
    q = q.order_by(Usuario.nome)
    items, pag = paginate(q, pagina, por_pagina)
    return ok([serialize_usuario(u) for u in items], pag)


@router.get("/{usuario_id}")
def get_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    return ok(serialize_usuario(user))


@router.put("/{usuario_id}")
def update_usuario(
    usuario_id: str,
    body: UsuarioUpdate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    _assert_pode_gerenciar(current, user)

    novo_role = user.role
    if body.role is not None:
        if body.role not in ROLES:
            return fail("Perfil inválido")
        _assert_pode_atribuir(current, body.role)
        novo_role = body.role
    if body.mfa_enabled is False and novo_role in MFA_REQUIRED_ROLES:
        return fail("MFA é obrigatório para este perfil")

    if body.email is not None and body.email != user.email:
        existente = db.query(Usuario).filter(Usuario.email == body.email, Usuario.id != usuario_id).first()
        if existente:
            return fail("Este e-mail já está cadastrado por outro usuário")
        user.email = body.email

    if body.nome is not None:
        user.nome = body.nome.strip()
    if novo_role != user.role:
        user.role = novo_role
        if novo_role in MFA_REQUIRED_ROLES:
            user.mfa_enabled = True
    if body.mfa_enabled is not None:
        user.mfa_enabled = body.mfa_enabled
        if not body.mfa_enabled:
            user.mfa_secret = None
    if body.senha:
        user.senha_hash = hash_password(body.senha)

    db.commit()
    db.refresh(user)
    log_operacao(db, current.id, "update", "usuario", user.id)
    return ok(serialize_usuario(user))


@router.delete("/{usuario_id}")
def delete_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    if current.id == usuario_id:
        return fail("Não é possível desativar a própria conta")

    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    _assert_pode_gerenciar(current, user)

    user.ativo = False
    db.commit()
    log_operacao(db, current.id, "delete", "usuario", user.id, f"email: {user.email}")
    return ok(None)


@router.post("/{usuario_id}/mfa/setup")
def mfa_setup_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    _assert_pode_gerenciar(current, user)
    secret = generate_mfa_secret()
    return ok(mfa_provisioning_data(user.email, secret))


@router.post("/{usuario_id}/mfa/enable")
@router.post("/{usuario_id}/mfa/habilitar")
def mfa_enable_usuario(
    usuario_id: str,
    body: MfaEnableRequest | None = None,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    _assert_pode_gerenciar(current, user)

    if body and body.codigo:
        if not verify_totp_code(body.secret, body.codigo):
            return fail("Código MFA inválido")
        user.mfa_secret = body.secret

    user.mfa_enabled = True
    db.commit()
    db.refresh(user)
    log_operacao(db, current.id, "update", "usuario", user.id, "mfa_enable")
    return ok(serialize_usuario(user))


@router.delete("/{usuario_id}/mfa")
@router.post("/{usuario_id}/mfa/desabilitar")
def mfa_reset_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    _assert_pode_gerenciar(current, user)
    reset_mfa(user)
    db.commit()
    db.refresh(user)
    log_operacao(db, current.id, "update", "usuario", user.id, "mfa_reset")
    return ok(serialize_usuario(user))


@router.post("")
def create_usuario(
    body: UsuarioCreate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    if body.role not in ROLES:
        return fail("Perfil inválido")
    _assert_pode_atribuir(current, body.role)
    if db.query(Usuario).filter(Usuario.email == body.email).first():
        return fail("E-mail já cadastrado")

    user = Usuario(
        nome=body.nome,
        email=body.email,
        senha_hash=hash_password(body.senha),
        role=body.role,
        cpf=body.cpf,
        mfa_enabled=body.role in MFA_REQUIRED_ROLES,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_operacao(db, current.id, "create", "usuario", user.id, body.email)
    return ok(serialize_usuario(user))
