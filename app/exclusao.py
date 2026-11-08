"""Exclusão lógica de contratos, checklists e problemas (US-015, ADR-0008).

O registro excluído continua no banco, com `excluido_em` e `excluido_por`, mas some de todas as consultas
de leitura do ORM: listagens, GET por ID, contagens, subconsultas e relacionamentos. O filtro é aplicado
num lugar só (evento `do_orm_execute`), para que uma rota nova não precise lembrar dele.

Os agendamentos de um contrato excluído também somem, porque não fazem sentido sem o contrato.
"""

from datetime import UTC, datetime

from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria

from app.models import AgendamentoVistoria, Checklist, Contrato, Problema, Usuario

_contratos = Contrato.__table__
# Tabela do Core, e não a entidade: o filtro de Contrato não pode ser aplicado dentro desta subconsulta
_ids_de_contratos_excluidos = select(_contratos.c.id).where(_contratos.c.excluido_em.isnot(None))


@event.listens_for(Session, "do_orm_execute")
def _ocultar_excluidos(estado) -> None:
    if not estado.is_select:
        return
    estado.statement = estado.statement.options(
        with_loader_criteria(Contrato, lambda cls: cls.excluido_em.is_(None), include_aliases=True),
        with_loader_criteria(Checklist, lambda cls: cls.excluido_em.is_(None), include_aliases=True),
        with_loader_criteria(Problema, lambda cls: cls.excluido_em.is_(None), include_aliases=True),
        with_loader_criteria(
            AgendamentoVistoria,
            lambda cls: cls.contrato_id.notin_(_ids_de_contratos_excluidos),
            include_aliases=True,
        ),
    )


def marcar_excluido(registro: Contrato | Checklist | Problema, user: Usuario) -> None:
    """Marca o registro como excluído por `user`. Não faz commit."""
    registro.excluido_em = datetime.now(UTC).replace(tzinfo=None)
    registro.excluido_por = user.id
