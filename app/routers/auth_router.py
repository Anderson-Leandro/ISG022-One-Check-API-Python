from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth import (
    MFA_REQUIRED_ROLES,
    conferir_credenciais,
    create_access_token,
    create_mfa_setup_token,
    create_refresh_token,
    create_temp_token,
    decode_token,
    encerrar_sessoes,
    generate_mfa_secret,
    hash_password,
    mfa_provisioning_data,
    mfa_self_disable_error,
    mfa_setup_required,
    mfa_troca_error,
    needs_mfa,
    nova_sessao,
    reset_mfa,
    revoke_refresh_token,
    sessao_vigente,
    usuario_to_dict,
    verify_refresh_token,
    verify_totp,
    verify_totp_code,
)
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Usuario
from app.rate_limit import Tentativas
from app.schemas import (
    LoginRequest,
    MfaActivateLoginRequest,
    MfaActivateRequest,
    MfaDisableRequest,
    MfaDisableSelfRequest,
    MfaVerifyRequest,
    RefreshRequest,
    fail,
    ok,
)
from app.serializers import log_operacao

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # Verificado antes da senha: durante o bloqueio nem a senha correta é aceita
    tentativas = Tentativas(request, "login", body.email.strip().lower())
    tentativas.verificar()

    user = db.query(Usuario).filter(Usuario.email == body.email, Usuario.ativo == True).first()
    if not conferir_credenciais(user, body.senha):
        tentativas.falhou()
        log_operacao(db, None, "login_falho", "usuario", None, f"email: {body.email}")
        return fail("Credenciais inválidas")
    tentativas.sucesso()

    if needs_mfa(user):
        temp = create_temp_token(user.id, user.token_version)
        return ok({
            "mfa_required": True,
            "temp_token": temp,
            "mfa_token": temp,
        })

    if mfa_setup_required(user):
        temp = create_mfa_setup_token(user.id, user.token_version)
        return ok({
            "mfa_setup_required": True,
            "temp_token": temp,
            "mfa_token": temp,
        })

    access = create_access_token(user.id, user.role, user.token_version)
    refresh = create_refresh_token(db, user.id)
    log_operacao(db, user.id, "login", "usuario", user.id, f"email: {user.email}")
    return ok({
        "access_token": access,
        "refresh_token": refresh,
        "usuario": usuario_to_dict(user),
    })


@router.post("/mfa/verify")
def mfa_verify(body: MfaVerifyRequest, request: Request, db: Session = Depends(get_db)):
    payload = decode_token(body.temp_token)
    if not payload or payload.get("type") != "mfa":
        return fail("Token MFA inválido ou expirado")

    user = db.query(Usuario).filter(Usuario.id == payload["sub"], Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    if not sessao_vigente(payload, user):
        return fail("Token MFA inválido ou expirado")

    # A conta (e não o temp_token) é a chave: um novo login não zera as tentativas
    tentativas = Tentativas(request, "mfa", user.id)
    tentativas.verificar()
    if not verify_totp(user, body.codigo.strip()):
        tentativas.falhou()
        log_operacao(db, user.id, "mfa_falho", "usuario", user.id, "via: mfa")
        return fail("Código MFA inválido")
    tentativas.sucesso()

    access = create_access_token(user.id, user.role, user.token_version)
    refresh = create_refresh_token(db, user.id)
    log_operacao(db, user.id, "mfa_verify", "usuario", user.id, "via: mfa")
    return ok({
        "access_token": access,
        "refresh_token": refresh,
        "usuario": usuario_to_dict(user),
    })


@router.get("/mfa/setup-login")
def setup_login(temp_token: str = Query(...), db: Session = Depends(get_db)):
    # Só o token de primeiro acesso serve aqui; o de verificação (type "mfa") é emitido
    # para quem já tem autenticador, e aceitá-lo permitiria trocar o segredo só com a senha
    payload = decode_token(temp_token)
    if not payload or payload.get("type") != "mfa_setup":
        raise HTTPException(status_code=401, detail="Token MFA inválido ou expirado")

    user = db.query(Usuario).filter(Usuario.id == payload["sub"], Usuario.ativo == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not sessao_vigente(payload, user):
        raise HTTPException(status_code=401, detail="Token MFA inválido ou expirado")

    # Revalida no momento da chamada: o token vale 10 min e pode ser reutilizado após a ativação
    if not mfa_setup_required(user):
        raise HTTPException(status_code=409, detail="MFA já configurado para este usuário")

    secret = generate_mfa_secret()
    user.mfa_secret_pendente = secret
    db.commit()
    db.refresh(user)
    return ok(mfa_provisioning_data(user.email, secret))


@router.post("/mfa/activate-login")
def activate_login(body: MfaActivateLoginRequest, request: Request, db: Session = Depends(get_db)):
    payload = decode_token(body.temp_token)
    if not payload or payload.get("type") != "mfa_setup":
        return fail("Token MFA inválido ou expirado")

    user = db.query(Usuario).filter(Usuario.id == payload["sub"], Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado")
    if not sessao_vigente(payload, user):
        return fail("Token MFA inválido ou expirado")

    if not mfa_setup_required(user):
        return fail("MFA já configurado para este usuário")

    tentativas = Tentativas(request, "mfa", user.id)
    tentativas.verificar()
    if not user.mfa_secret_pendente or not verify_totp_code(user.mfa_secret_pendente, body.codigo):
        tentativas.falhou()
        log_operacao(db, user.id, "mfa_falho", "usuario", user.id, "via: mfa_setup")
        return fail("Código MFA inválido")
    tentativas.sucesso()

    user.mfa_secret = user.mfa_secret_pendente
    user.mfa_secret_pendente = None
    user.mfa_enabled = True
    db.commit()
    db.refresh(user)

    access = create_access_token(user.id, user.role, user.token_version)
    refresh = create_refresh_token(db, user.id)
    log_operacao(db, user.id, "login", "usuario", user.id, "via: mfa_setup")
    return ok({
        "access_token": access,
        "refresh_token": refresh,
        "usuario": usuario_to_dict(user),
    })


@router.post("/mfa/setup")
@router.get("/mfa/setup", deprecated=True)
def mfa_setup(user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    # O segredo fica pendente até o /mfa/activate confirmar o código: abandonar o setup
    # não invalida o autenticador em uso
    secret = generate_mfa_secret()
    user.mfa_secret_pendente = secret
    db.commit()
    db.refresh(user)
    return ok(mfa_provisioning_data(user.email, secret))


@router.post("/mfa/activate")
def mfa_activate(
    body: MfaActivateRequest,
    request: Request,
    user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.mfa_secret_pendente:
        return fail("Configuração MFA não encontrada")

    tentativas = Tentativas(request, "reauth", user.id)
    tentativas.verificar()
    erro = mfa_troca_error(user, body.codigo_atual)
    if erro:
        tentativas.falhou()
        return fail(erro)

    if not verify_totp_code(user.mfa_secret_pendente, body.codigo.strip()):
        return fail("Código MFA inválido")

    user.mfa_secret = user.mfa_secret_pendente
    user.mfa_secret_pendente = None
    user.mfa_enabled = True
    encerrar_sessoes(db, user)
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "mfa_activate", "usuario", user.id)
    return ok({"mensagem": "MFA ativado com sucesso", "sessao": nova_sessao(db, user)})


@router.post("/mfa/disable")
def mfa_disable(
    body: MfaDisableRequest,
    current_admin: Usuario = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    # O próprio MFA não se reseta por aqui: exige outro admin (separação de deveres)
    if body.usuario_id == current_admin.id:
        raise HTTPException(status_code=403, detail="Não é possível resetar o próprio MFA")

    target = db.query(Usuario).filter(Usuario.id == body.usuario_id, Usuario.ativo == True).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    reset_mfa(target)
    encerrar_sessoes(db, target)
    db.commit()
    db.refresh(target)
    log_operacao(db, current_admin.id, "mfa_disable", "usuario", target.id)
    return ok({"mensagem": "MFA desativado com sucesso"})


@router.post("/mfa/habilitar")
def mfa_habilitar(
    user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.mfa_enabled = True
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "mfa_enable", "usuario", user.id)
    return ok({"mensagem": "MFA habilitado. Configure o autenticador no próximo login."})


@router.post("/mfa/desabilitar")
def mfa_desabilitar(
    body: MfaDisableSelfRequest,
    request: Request,
    user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
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

    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_secret_pendente = None
    encerrar_sessoes(db, user)
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "mfa_disable", "usuario", user.id)
    return ok({"mensagem": "MFA desativado com sucesso", "sessao": nova_sessao(db, user)})


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    user = verify_refresh_token(db, body.refresh_token)
    if not user:
        return fail("Refresh token inválido ou expirado")

    access = create_access_token(user.id, user.role, user.token_version)
    new_refresh = create_refresh_token(db, user.id)
    revoke_refresh_token(db, body.refresh_token)
    return ok({"access_token": access, "refresh_token": new_refresh})


@router.post("/logout")
def logout(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    body: RefreshRequest | None = None,
):
    if body is not None and body.refresh_token:
        revoke_refresh_token(db, body.refresh_token)
    log_operacao(db, user.id, "logout", "usuario", user.id)
    return ok(None)
