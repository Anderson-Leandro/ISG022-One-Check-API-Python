"""Direitos do titular (LGPD, art. 18): exportação e anonimização dos próprios dados (SEC-028, ADR-0017).

Decisão do PO em 2026-11-11: autoatendimento, sempre sobre o próprio usuário (não há rota com o id de outro).
- Exportação: os dados pessoais do usuário e os registros ligados a ele, em JSON.
- Anonimização: nome, e-mail e CPF deixam de identificar a pessoa, a conta é desativada e as sessões
  são revogadas. Contratos, vistorias, aceites e atualizações continuam (laudos válidos), apontando para o
  mesmo id, que passa a mostrar "Usuário removido". O log de auditoria continua (append-only, SEC-025,
  e registro de acesso do Marco Civil, art. 15), guardando o id e o IP até a retenção.
"""

import secrets

from sqlalchemy.orm import Session

from app.auth import encerrar_sessoes, hash_password
from app.models import AceiteChecklist, AtualizacaoProblema, Checklist, Contrato, LogOperacao, Usuario
from app.serializers import serialize_usuario

NOME_ANONIMIZADO = "Usuário removido"


def _data(valor):
    return valor.isoformat() if valor else None


def exportar(db: Session, user: Usuario) -> dict:
    """Os dados pessoais do próprio usuário e os registros em que ele aparece."""
    contratos = db.query(Contrato).filter(Contrato.locatario_id == user.id).order_by(Contrato.created_at).all()
    vistorias = db.query(Checklist).filter(Checklist.vistoriador_id == user.id).order_by(Checklist.created_at).all()
    aceites = (
        db.query(AceiteChecklist)
        .filter(AceiteChecklist.locatario_id == user.id)
        .order_by(AceiteChecklist.created_at)
        .all()
    )
    atualizacoes = (
        db.query(AtualizacaoProblema)
        .filter(AtualizacaoProblema.autor_id == user.id)
        .order_by(AtualizacaoProblema.created_at)
        .all()
    )
    logs = db.query(LogOperacao).filter(LogOperacao.usuario_id == user.id).order_by(LogOperacao.created_at).all()
    # O que outra pessoa fez sobre a conta (criação, desativação, MFA), sem o id nem o IP de quem fez
    sobre_a_conta = (
        db.query(LogOperacao)
        .filter(
            LogOperacao.entidade == "usuario",
            LogOperacao.entidade_id == user.id,
            (LogOperacao.usuario_id != user.id) | LogOperacao.usuario_id.is_(None),
        )
        .order_by(LogOperacao.created_at)
        .all()
    )
    return {
        "usuario": serialize_usuario(user, cpf_completo=True),
        "contratos": [
            {
                "id": c.id,
                "imovel_id": c.imovel_id,
                "data_inicio": _data(c.data_inicio),
                "data_fim": _data(c.data_fim),
                "valor_mensal": float(c.valor_mensal) if c.valor_mensal is not None else None,
                "status": c.status,
            }
            for c in contratos
        ],
        "vistorias_realizadas": [
            {"id": v.id, "contrato_id": v.contrato_id, "tipo": v.tipo, "data_vistoria": _data(v.data_vistoria)}
            for v in vistorias
        ],
        "aceites": [
            {
                "checklist_id": a.checklist_id,
                "status": a.status,
                "motivo_rejeicao": a.motivo_rejeicao,
                "created_at": _data(a.created_at),
            }
            for a in aceites
        ],
        "atualizacoes_de_problema": [
            {"problema_id": a.problema_id, "descricao": a.descricao, "created_at": _data(a.created_at)}
            for a in atualizacoes
        ],
        "logs": [
            {
                "acao": log.acao,
                "entidade": log.entidade,
                "entidade_id": log.entidade_id,
                "detalhes": log.detalhes,
                "payload": log.payload,
                "ip": log.ip,
                "created_at": _data(log.created_at),
            }
            for log in logs
        ],
        "eventos_sobre_a_conta": [
            {"acao": log.acao, "detalhes": log.detalhes, "created_at": _data(log.created_at)} for log in sobre_a_conta
        ],
    }


def e_ultimo_admin(db: Session, user: Usuario) -> bool:
    """Trava as linhas dos admins ativos (no PostgreSQL) até o commit: dois admins se anonimizando ao mesmo
    tempo não deixam o sistema sem nenhum."""
    if user.role != "admin":
        return False
    admins = (
        db.query(Usuario.id)
        .filter(Usuario.role == "admin", Usuario.ativo == True)  # noqa: E712
        .order_by(Usuario.id)
        .with_for_update()
        .all()
    )
    return all(a.id == user.id for a in admins)


def anonimizar(db: Session, user: Usuario) -> None:
    """Apaga o que identifica a pessoa e inutiliza o acesso. Sem commit: quem chama confirma."""
    user.nome = NOME_ANONIMIZADO
    user.email = f"removido-{user.id}@anonimizado.invalid"
    user.cpf = None
    user.senha_hash = hash_password(secrets.token_urlsafe(32))
    user.mfa_secret = None
    user.mfa_secret_pendente = None
    user.mfa_enabled = False
    user.ativo = False
    encerrar_sessoes(db, user)
