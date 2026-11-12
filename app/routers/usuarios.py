from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auditoria import campos_alterados
from app.auth import (
    MFA_REQUIRED_ROLES,
    PRIVILEGED_ROLES,
    ROLES,
    encerrar_sessoes,
    generate_mfa_secret,
    hash_password,
    mfa_provisioning_data,
    mfa_self_disable_error,
    mfa_troca_error,
    nova_sessao,
    reset_mfa,
    verify_password,
    verify_totp_code,
)
from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Usuario
from app.rate_limit import Tentativas
from app.respostas import UsuarioResposta, documentar
from app.schemas import (
    AlterarSenhaRequest,
    AnonimizarMeRequest,
    MfaDisableSelfRequest,
    MfaEnableRequest,
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioUpdateMe,
    fail,
    ok,
)
from app.senhas_vazadas import exigir_senha_nao_vazada
from app.serializers import log_operacao, paginate, serialize_usuario
from app.titular import anonimizar, e_ultimo_admin, exportar

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


@router.get("/me", responses=documentar(UsuarioResposta, erros=(401,)))
def me(user: Usuario = Depends(get_current_user)):
    return ok(serialize_usuario(user, cpf_completo=True))


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
            return fail("Nome é obrigatório", erros={"nome": "Nome é obrigatório"}, status_code=422)
        user.nome = nome

    if body.senha_nova:
        if not body.senha_atual:
            return fail("Informe a senha atual", erros={"senha_atual": "Informe a senha atual"}, status_code=422)
        tentativas = Tentativas(request, "reauth", user.id)
        tentativas.verificar()
        if not verify_password(body.senha_atual, user.senha_hash):
            tentativas.falhou()
            return fail("Senha atual incorreta", status_code=403)
        tentativas.sucesso()
        if vazada := exigir_senha_nao_vazada(body.senha_nova, "senha_nova"):
            return vazada
        user.senha_hash = hash_password(body.senha_nova)
    alterados = campos_alterados(user)
    if body.senha_nova:
        encerrar_sessoes(db, user)

    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "perfil", payload={"campos": alterados})
    dados = serialize_usuario(user, cpf_completo=True)
    if body.senha_nova:
        dados["sessao"] = nova_sessao(db, user)
    return ok(dados)


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
        return fail("Senha atual incorreta", status_code=403)
    tentativas.sucesso()
    if vazada := exigir_senha_nao_vazada(body.nova_senha, "nova_senha"):
        return vazada

    user.senha_hash = hash_password(body.nova_senha)
    encerrar_sessoes(db, user)
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "alteracao_de_senha")
    return ok({"mensagem": "Senha alterada com sucesso", "sessao": nova_sessao(db, user)})


@router.get("/me/dados")
def exportar_meus_dados(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Os próprios dados pessoais, em JSON (LGPD, art. 18, II e V; SEC-028). Só do usuário autenticado."""
    dados = exportar(db, user)
    log_operacao(db, user.id, "exportacao_de_dados", "usuario", user.id)
    return ok(dados)


@router.post("/me/anonimizar")
def anonimizar_me(
    body: AnonimizarMeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Anonimiza a própria conta e a desativa (LGPD, art. 18, IV e VI; SEC-028, ADR-0017). Não tem volta."""
    tentativas = Tentativas(request, "reauth", user.id)
    tentativas.verificar()
    erro = mfa_self_disable_error(user, body.senha, body.codigo)
    if erro:
        tentativas.falhou()
        return fail(erro, status_code=403)
    tentativas.sucesso()
    if e_ultimo_admin(db, user):
        return fail("O último admin ativo não pode anonimizar a própria conta", status_code=409)

    anonimizar(db, user)
    # O log entra no mesmo commit da anonimização, que não tem volta. Sem dados pessoais: só o id
    log_operacao(db, user.id, "anonimizacao", "usuario", user.id)
    return ok({"mensagem": "Dados anonimizados e conta desativada"})


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
        return fail(erro, status_code=403)
    if not verify_totp_code(body.secret, body.codigo):
        return fail("Código MFA inválido", erros={"codigo": "Código MFA inválido"}, status_code=422)
    user.mfa_secret = body.secret
    user.mfa_enabled = True
    encerrar_sessoes(db, user)
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "mfa_enable")
    return ok({**serialize_usuario(user, cpf_completo=True), "sessao": nova_sessao(db, user)})


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
        return fail(erro, status_code=403)
    tentativas.sucesso()

    user.mfa_secret = None
    user.mfa_secret_pendente = None
    user.mfa_enabled = False
    encerrar_sessoes(db, user)
    db.commit()
    db.refresh(user)
    log_operacao(db, user.id, "update", "usuario", user.id, "mfa_disable")
    return ok({**serialize_usuario(user, cpf_completo=True), "sessao": nova_sessao(db, user)})


@router.get("", responses=documentar(UsuarioResposta, lista=True, erros=(401, 403)))
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


@router.get("/{usuario_id}", responses=documentar(UsuarioResposta, erros=(401, 403, 404)))
def get_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado", status_code=404)
    return ok(serialize_usuario(user, cpf_completo=True))


@router.put("/{usuario_id}")
def update_usuario(
    usuario_id: str,
    body: UsuarioUpdate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado", status_code=404)
    _assert_pode_gerenciar(current, user)
    if vazada := exigir_senha_nao_vazada(body.senha, "senha"):
        return vazada

    novo_role = user.role
    if body.role is not None:
        if body.role not in ROLES:
            return fail("Perfil inválido", erros={"role": "Perfil inválido"}, status_code=422)
        _assert_pode_atribuir(current, body.role)
        novo_role = body.role
    if body.mfa_enabled is False and novo_role in MFA_REQUIRED_ROLES:
        return fail(
            "MFA é obrigatório para este perfil",
            erros={"mfa_enabled": "MFA é obrigatório para este perfil"},
            status_code=422,
        )

    if body.email is not None and body.email != user.email:
        existente = db.query(Usuario).filter(Usuario.email == body.email, Usuario.id != usuario_id).first()
        if existente:
            return fail("Este e-mail já está cadastrado por outro usuário", status_code=409)
        user.email = body.email

    if body.nome is not None:
        user.nome = body.nome.strip()
    # Perfil, MFA ou senha alterados pelo gestor/admin encerram as sessões do usuário
    credencial_alterada = False
    if novo_role != user.role:
        user.role = novo_role
        credencial_alterada = True
        if novo_role in MFA_REQUIRED_ROLES:
            user.mfa_enabled = True
    if body.mfa_enabled is not None:
        credencial_alterada = credencial_alterada or body.mfa_enabled != user.mfa_enabled
        user.mfa_enabled = body.mfa_enabled
        if not body.mfa_enabled:
            user.mfa_secret = None
    if body.senha:
        user.senha_hash = hash_password(body.senha)
        credencial_alterada = True
    alterados = campos_alterados(user)
    if credencial_alterada:
        encerrar_sessoes(db, user)

    db.commit()
    db.refresh(user)
    log_operacao(db, current.id, "update", "usuario", user.id, payload={"campos": alterados})
    return ok(serialize_usuario(user))


@router.delete("/{usuario_id}")
def delete_usuario(
    usuario_id: str,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    if current.id == usuario_id:
        return fail("Não é possível desativar a própria conta", status_code=403)

    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado", status_code=404)
    _assert_pode_gerenciar(current, user)

    user.ativo = False
    encerrar_sessoes(db, user)
    db.commit()
    log_operacao(db, current.id, "delete", "usuario", user.id)  # sem o e-mail (SEC-028)
    return ok(None)


# Não há setup de MFA para outro usuário: quem conhece o segredo gera os códigos.
# Admin/gestor só exigem (enable) ou resetam o MFA; o segredo é criado no login do próprio usuário
@router.post("/{usuario_id}/mfa/enable")
@router.post("/{usuario_id}/mfa/habilitar")
def mfa_enable_usuario(
    usuario_id: str,
    body: dict | None = Body(None),
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return fail("Usuário não encontrado", status_code=404)
    _assert_pode_gerenciar(current, user)
    if body and ("secret" in body or "codigo" in body):
        msg = "O autenticador é configurado pelo próprio usuário no próximo login"
        return JSONResponse(status_code=422, content={"sucesso": False, "erro": msg, "erros": {"secret": msg}})

    if not user.mfa_enabled:
        user.mfa_enabled = True
        encerrar_sessoes(db, user)
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
        return fail("Usuário não encontrado", status_code=404)
    _assert_pode_gerenciar(current, user)
    reset_mfa(user)
    encerrar_sessoes(db, user)
    db.commit()
    db.refresh(user)
    log_operacao(db, current.id, "update", "usuario", user.id, "mfa_reset")
    return ok(serialize_usuario(user))


@router.post("", responses=documentar(UsuarioResposta, erros=(401, 403, 409, 422)))
def create_usuario(
    body: UsuarioCreate,
    db: Session = Depends(get_db),
    current: Usuario = Depends(require_roles("admin", "gestor")),
):
    if body.role not in ROLES:
        return fail("Perfil inválido", erros={"role": "Perfil inválido"}, status_code=422)
    _assert_pode_atribuir(current, body.role)
    if db.query(Usuario).filter(Usuario.email == body.email).first():
        return fail("E-mail já cadastrado", status_code=409)
    if vazada := exigir_senha_nao_vazada(body.senha, "senha"):
        return vazada

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
    log_operacao(db, current.id, "create", "usuario", user.id)  # sem o e-mail (SEC-028)
    return ok(serialize_usuario(user))
