"""Totais atuais do banco (somente leitura)."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AgendamentoVistoria,
    Checklist,
    Contrato,
    Endereco,
    Imovel,
    ItemVistoria,
    Problema,
    Usuario,
)


def get_data_status(db: Session) -> dict:
    enderecos_com_coords = (
        db.query(Endereco)
        .filter(Endereco.latitude.isnot(None), Endereco.longitude.isnot(None))
        .count()
    )
    return {
        "usuarios": db.query(Usuario).count(),
        "imoveis": db.query(Imovel).count(),
        "enderecos": db.query(Endereco).count(),
        "enderecos_com_coordenadas": enderecos_com_coords,
        "contratos": db.query(Contrato).count(),
        "checklists": db.query(Checklist).count(),
        "agendamentos": db.query(AgendamentoVistoria).count(),
        "problemas": db.query(Problema).count(),
        "itens_vistoria": db.query(ItemVistoria).count(),
        # Os quatro status do fluxo sempre aparecem; um status fora do fluxo (dado antigo) aparece também,
        # em vez de sumir da contagem
        "checklists_por_status": {
            **{status: 0 for status in ("em_preenchimento", "pendente_aceite", "aceito", "rejeitado")},
            **dict(db.query(Checklist.status, func.count(Checklist.id)).group_by(Checklist.status).all()),
        },
    }
