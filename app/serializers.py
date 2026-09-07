from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import PUBLIC_BASE_URL
from typing import Any
from app.models import (
    AceiteChecklist,
    AtualizacaoProblema,
    Checklist,
    ChecklistItem,
    ChecklistItemFoto,
    Contrato,
    Endereco,
    Imovel,
    ImovelComodo,
    ItemVistoria,
    LogOperacao,
    Problema,
    Usuario,
)


def foto_url(arquivo: str | None) -> str | None:
    if not arquivo:
        return None
    if arquivo.startswith("http://") or arquivo.startswith("https://") or arquivo.startswith("/"):
        return arquivo
    return f"/api/v1/uploads/{arquivo}"


def serialize_foto(f: ChecklistItemFoto) -> dict:
    return {"id": f.id, "url": foto_url(f.arquivo)}


def serialize_aceite(a: AceiteChecklist | None) -> dict | None:
    if not a:
        return None
    return {
        "id": a.id,
        "checklist_id": a.checklist_id,
        "locatario_id": a.locatario_id,
        "status": a.status,
        "motivo_rejeicao": a.motivo_rejeicao,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def serialize_atualizacao_problema(at: AtualizacaoProblema) -> dict:
    return {
        "id": at.id,
        "problema_id": at.problema_id,
        "autor_id": at.autor_id,
        "descricao": at.descricao,
        "foto_url": at.foto_url,
        "created_at": at.created_at.isoformat() if at.created_at else None,
    }


def serialize_problema(pb: Problema) -> dict:
    return {
        "id": pb.id,
        "contrato_id": pb.contrato_id,
        "comodo_id": pb.comodo_id,
        "titulo": pb.titulo,
        "descricao": pb.descricao,
        "foto_url": pb.foto_url,
        "prioridade": pb.prioridade,
        "status": pb.status,
        "created_at": pb.created_at.isoformat() if pb.created_at else None,
        "atualizacoes": [serialize_atualizacao_problema(a) for a in getattr(pb, "atualizacoes", [])],
    }


def serialize_item(item: ChecklistItem) -> dict:
    return {
        "id": item.id,
        "checklist_id": item.checklist_id,
        "comodo_id": item.comodo_id,
        "item_vistoria_id": item.item_vistoria_id,
        "estado": item.estado,
        "observacao": item.observacao,
        "fotos": [serialize_foto(f) for f in item.fotos],
    }


def serialize_comodo(c: ImovelComodo) -> dict:
    return {
        "id": c.id,
        "imovel_id": c.imovel_id,
        "tipo": c.tipo,
        "descricao": c.descricao,
        "nome": c.nome,
    }


def serialize_checklist(
    ck: Checklist,
    include_itens: bool = False,
    comodos: list[ImovelComodo] | None = None,
) -> dict:
    data = {
        "id": ck.id,
        "contrato_id": ck.contrato_id,
        "vistoriador_id": ck.vistoriador_id,
        "tipo": ck.tipo,
        "status": ck.status,
        "data_vistoria": ck.data_vistoria.isoformat() if ck.data_vistoria else None,
        "created_at": ck.created_at.isoformat() if ck.created_at else None,
        "aceite": serialize_aceite(ck.aceite) if hasattr(ck, "aceite") and ck.aceite else None,
    }
    if include_itens:
        data["itens"] = [serialize_item(i) for i in ck.itens]
    if comodos is not None:
        data["comodos"] = [serialize_comodo(c) for c in comodos]
    return data


def serialize_endereco(end: Endereco | None) -> dict | None:
    if not end:
        return None
    return {
        "rua": getattr(end, "rua", None),
        "logradouro": getattr(end, "rua", None),
        "numero": getattr(end, "numero", None),
        "complemento": getattr(end, "complemento", None),
        "bloco": getattr(end, "bloco", None),
        "andar": getattr(end, "andar", None),
        "bairro": getattr(end, "bairro", None),
        "cidade": getattr(end, "cidade", None),
        "estado": getattr(end, "estado", None),
        "cep": getattr(end, "cep", None),
        "latitude": getattr(end, "latitude", None),
        "longitude": getattr(end, "longitude", None),
    }


def serialize_imovel(im: Imovel, *, include_endereco: bool = False) -> dict:
    data = {
        "id": im.id,
        "codigo": im.codigo,
        "titulo": im.titulo,
        "tipo": im.tipo,
        "tamanho": im.tamanho,
        "garagem": im.garagem,
        "garagem_vagas": im.garagem_vagas,
        "status": im.status,
        "observacoes": im.observacoes,
        "ativo": im.ativo if hasattr(im, "ativo") else True,
        "created_at": im.created_at.isoformat() if im.created_at else None,
    }
    if include_endereco:
        end = im.endereco if hasattr(im, "endereco") else None
        data["endereco"] = serialize_endereco(end)
    return data


def serialize_contrato(ct: Contrato) -> dict:
    return {
        "id": ct.id,
        "imovel_id": ct.imovel_id,
        "locatario_id": ct.locatario_id,
        "data_inicio": ct.data_inicio.isoformat(),
        "data_fim": ct.data_fim.isoformat(),
        "valor_mensal": float(ct.valor_mensal) if ct.valor_mensal is not None else None,
        "status": ct.status,
        "created_at": ct.created_at.isoformat() if ct.created_at else None,
    }


def serialize_agendamento(ag) -> dict:
    return {
        "id": ag.id,
        "contrato_id": ag.contrato_id,
        "tipo": ag.tipo,
        "data_agendada": ag.data_agendada.isoformat() if ag.data_agendada else None,
        "observacao": ag.observacao,
        "created_at": ag.created_at.isoformat() if ag.created_at else None,
    }


def serialize_usuario(u: Usuario) -> dict:
    return {
        "id": u.id,
        "nome": u.nome,
        "email": u.email,
        "role": u.role,
        "cpf": u.cpf,
        "mfa_enabled": bool(u.mfa_enabled),
        "mfa_configurado": bool(u.mfa_secret),
        "mfa_ativo": bool(u.mfa_enabled and u.mfa_secret),
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def paginate(query, pagina: int, por_pagina: int):
    total = query.count()
    items = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()
    return items, {
        "total": total,
        "pagina": pagina,
        "itensPorPagina": por_pagina,
    }


def log_operacao(
    db: Session,
    usuario_id: str | None,
    acao: str,
    entidade: str | None = None,
    entidade_id: str | None = None,
    detalhes: str | None = None,
    payload: Any = None,
    ip: str | None = None,
) -> None:
    sanitized_payload = payload
    if isinstance(payload, dict):
        sanitized_payload = {
            k: v for k, v in payload.items()
            if k not in ("senha", "senha_hash", "mfa_secret", "password", "secret")
        }
    db.add(
        LogOperacao(
            usuario_id=usuario_id,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            detalhes=detalhes,
            payload=sanitized_payload,
            ip=ip,
        )
    )
    db.commit()


def get_comodos_for_checklist(db: Session, checklist: Checklist) -> list[ImovelComodo]:
    contrato = db.query(Contrato).filter(Contrato.id == checklist.contrato_id).first()
    if not contrato:
        return []
    return (
        db.query(ImovelComodo)
        .filter(ImovelComodo.imovel_id == contrato.imovel_id)
        .order_by(ImovelComodo.tipo)
        .all()
    )


def ensure_default_comodos(db: Session, imovel_id: str) -> None:
    existing = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == imovel_id).count()
    if existing > 0:
        return
    defaults = [
        ("Sala", "sala"),
        ("Cozinha", "cozinha"),
        ("Quarto 1", "quarto"),
        ("Banheiro", "banheiro"),
    ]
    for nome, tipo in defaults:
        db.add(ImovelComodo(imovel_id=imovel_id, tipo=tipo, nome=nome, descricao=nome))
    db.commit()
