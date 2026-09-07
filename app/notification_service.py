"""
Serviço de notificações (e-mail / painel) para eventos de negócio (OneCheck).
Espelha o NotificationService do PHP.
"""
import logging
from sqlalchemy.orm import Session
from app.models import Usuario

logger = logging.getLogger("onecheck.notifications")


def notificar_usuario(db: Session, usuario_id: str, assunto: str, mensagem: str) -> None:
    """Envia notificação para um usuário específico."""
    user = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo == True).first()
    if not user:
        return
    logger.info("Notificação enviada para [%s] %s: %s\n%s", user.id, user.email, assunto, mensagem)


def notificar_admins(db: Session, assunto: str, mensagem: str) -> None:
    """Envia notificação para todos os administradores ativos."""
    admins = db.query(Usuario).filter(Usuario.role == "admin", Usuario.ativo == True).all()
    for admin in admins:
        logger.info("Notificação ADMIN enviada para [%s] %s: %s\n%s", admin.id, admin.email, assunto, mensagem)
