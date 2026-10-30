"""Seed completo + modo expand para enriquecer banco existente."""
import secrets
from datetime import date, timedelta

import pyotp
from sqlalchemy.orm import Session

from app.auth import MFA_REQUIRED_ROLES, encerrar_sessoes, hash_password, reset_mfa, verify_password
from app.config import IS_DEV
from app.models import (
    AgendamentoVistoria,
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
    RefreshToken,
    Usuario,
)
from app.serializers import ensure_default_comodos, log_operacao

# Credenciais fixas de demonstração: estão no repositório público, então só valem em APP_ENV=development/test.
# Fora disso o seed gera senha aleatória e deixa o MFA para configurar no primeiro login.
MFA_SECRET_DEV = "JBSWY3DPEHPK3PXP"
SENHAS_DEV = {
    "admin@onecheck.local": "admin123",
    "gestor@onecheck.local": "gestor123",
    "vistoriador@onecheck.local": "vistor123",
    "ana.vistoriadora@onecheck.local": "vistor123",
    "locatario@onecheck.local": "locat123",
    "pedro.locatario@onecheck.local": "locat123",
    "julia.locatario@onecheck.local": "locat123",
}


def _novo_usuario(nome: str, email: str, role: str, credenciais: list[dict]) -> Usuario:
    """Cria o usuário de seed e anota a senha em `credenciais` (exibida uma única vez na resposta)."""
    mfa = role in MFA_REQUIRED_ROLES
    if IS_DEV:
        senha, mfa_secret = SENHAS_DEV[email], MFA_SECRET_DEV if mfa else None
    else:
        senha, mfa_secret = secrets.token_urlsafe(16), None
    credenciais.append({"email": email, "senha": senha, "mfa": mfa})
    # Sem mfa_secret, perfis com MFA obrigatório configuram o autenticador no primeiro login
    return Usuario(
        nome=nome, email=email, senha_hash=hash_password(senha), role=role,
        mfa_enabled=mfa, mfa_secret=mfa_secret,
    )


def _info_mfa() -> dict:
    if IS_DEV:
        return {"mfa_secret": MFA_SECRET_DEV, "mfa_codigo_atual": pyotp.TOTP(MFA_SECRET_DEV).now()}
    return {"mfa": "Perfis com MFA configuram o autenticador no primeiro login"}


def contas_com_credenciais_publicas(db: Session) -> list[Usuario]:
    """Usuários ativos que ainda usam a senha ou o segredo TOTP de demonstração publicados no repositório."""
    expostos = db.query(Usuario).filter(Usuario.ativo == True, Usuario.mfa_secret == MFA_SECRET_DEV).all()
    for user in db.query(Usuario).filter(Usuario.ativo == True, Usuario.email.in_(SENHAS_DEV)).all():
        if user not in expostos and verify_password(SENHAS_DEV[user.email], user.senha_hash):
            expostos.append(user)
    return expostos


def rotacionar_credenciais_publicas(db: Session) -> list[dict]:
    """Troca a senha, reseta o MFA e revoga as sessões das contas com credenciais públicas."""
    novas = []
    for user in contas_com_credenciais_publicas(db):
        senha = secrets.token_urlsafe(16)
        user.senha_hash = hash_password(senha)
        reset_mfa(user)
        encerrar_sessoes(db, user)
        log_operacao(db, None, "rotacao_credenciais", "usuario", user.id, "Credenciais de demonstração substituídas")
        novas.append({"email": user.email, "senha": senha, "mfa": user.mfa_enabled})
    db.commit()
    return novas


def _clear_all(db: Session) -> None:
    db.query(ChecklistItemFoto).delete()
    db.query(ChecklistItem).delete()
    db.query(Checklist).delete()
    db.query(AgendamentoVistoria).delete()
    db.query(Problema).delete()
    db.query(Contrato).delete()
    db.query(Endereco).delete()
    db.query(ImovelComodo).delete()
    db.query(Imovel).delete()
    db.query(ItemVistoria).delete()
    db.query(LogOperacao).delete()
    db.query(RefreshToken).delete()
    db.query(Usuario).delete()
    db.commit()


def _create_imovel_com_contrato(
    db: Session,
    *,
    codigo: str,
    titulo: str,
    tipo: str,
    tamanho: str,
    status_final: str,
    endereco: dict,
    locatario_id: str,
    vistoriador_id: str,
    valor: float,
    checklist_tipo: str = "inicial",
    checklist_status: str = "em_preenchimento",
    dias_contrato: int = 365,
    offset_dias: int = 0,
    problemas: list[dict] | None = None,
    preencher_itens: bool = False,
) -> dict:
    hoje = date.today() + timedelta(days=offset_dias)
    im = Imovel(
        codigo=codigo,
        titulo=titulo,
        tipo=tipo,
        tamanho=tamanho,
        garagem=True,
        garagem_vagas=1,
        status="disponivel",
    )
    db.add(im)
    db.flush()
    ensure_default_comodos(db, im.id)
    comodos = db.query(ImovelComodo).filter(ImovelComodo.imovel_id == im.id).all()
    itens_cat = db.query(ItemVistoria).limit(4).all()

    db.add(Endereco(imovel_id=im.id, **endereco))

    ct = Contrato(
        imovel_id=im.id,
        locatario_id=locatario_id,
        data_inicio=hoje,
        data_fim=hoje + timedelta(days=dias_contrato),
        valor_mensal=valor,
        status="ativo",
    )
    db.add(ct)
    db.flush()
    im.status = status_final if status_final != "disponivel" else "locado"

    for tipo_ag in ("inicial", "encerramento"):
        db.add(
            AgendamentoVistoria(
                contrato_id=ct.id,
                tipo=tipo_ag,
                data_agendada=hoje if tipo_ag == "inicial" else hoje + timedelta(days=dias_contrato),
                observacao=f"Vistoria {tipo_ag} — {titulo}",
            )
        )

    ck = Checklist(
        contrato_id=ct.id,
        vistoriador_id=vistoriador_id,
        tipo=checklist_tipo,
        status=checklist_status,
        data_vistoria=hoje,
    )
    db.add(ck)
    db.flush()

    if preencher_itens and comodos and itens_cat:
        estados = ["otimo", "bom", "regular", "ruim"]
        for i, comodo in enumerate(comodos[:3]):
            for j, cat in enumerate(itens_cat[:2]):
                db.add(
                    ChecklistItem(
                        checklist_id=ck.id,
                        comodo_id=comodo.id,
                        item_vistoria_id=cat.id,
                        estado=estados[(i + j) % len(estados)],
                        observacao=f"Verificado em {comodo.nome}",
                    )
                )

    for pb in problemas or []:
        db.add(Problema(contrato_id=ct.id, **pb))

    return {"imovel_id": im.id, "contrato_id": ct.id, "checklist_id": ck.id}


def _clear_data_keep_users(db: Session) -> None:
    db.query(ChecklistItemFoto).delete()
    db.query(ChecklistItem).delete()
    db.query(Checklist).delete()
    db.query(AgendamentoVistoria).delete()
    db.query(Problema).delete()
    db.query(Contrato).delete()
    db.query(Endereco).delete()
    db.query(ImovelComodo).delete()
    db.query(Imovel).delete()
    db.query(ItemVistoria).delete()
    db.query(LogOperacao).delete()
    db.query(RefreshToken).delete()
    db.commit()


def _populate_sample_data(
    db: Session,
    *,
    admin: Usuario,
    gestor: Usuario | None,
    vist1: Usuario,
    vist2: Usuario | None,
    loc1: Usuario,
    loc2: Usuario | None,
    loc3: Usuario | None,
) -> dict:
    catalog = [
        ("Piso", "estrutura"), ("Paredes", "estrutura"), ("Teto", "estrutura"),
        ("Portas", "acabamento"), ("Janelas", "acabamento"), ("Tomadas", "eletrica"),
        ("Iluminação", "eletrica"), ("Pintura", "acabamento"),
        ("Torneiras", "hidraulica"), ("Box", "banheiro"),
    ]
    for nome, cat in catalog:
        db.add(ItemVistoria(nome=nome, categoria=cat))
    db.flush()

    created = []
    vist_b = vist2 or vist1
    loc_b = loc2 or loc1
    loc_c = loc3 or loc1

    created.append(_create_imovel_com_contrato(
        db, codigo="IM-001", titulo="Apartamento Centro", tipo="Apartamento", tamanho="65m²",
        status_final="locado", locatario_id=loc1.id, vistoriador_id=vist1.id, valor=2500,
        endereco={"rua": "Rua das Flores", "numero": "100", "bairro": "Centro", "cidade": "São Paulo", "estado": "SP", "cep": "01001000", "latitude": -23.5505, "longitude": -46.6333},
        checklist_status="em_preenchimento", preencher_itens=True,
        problemas=[{"titulo": "Torneira pingando", "descricao": "Cozinha", "prioridade": "normal", "status": "aberto"}],
    ))

    created.append(_create_imovel_com_contrato(
        db, codigo="IM-002", titulo="Casa Jardim América", tipo="Casa", tamanho="120m²",
        status_final="locado", locatario_id=loc_b.id, vistoriador_id=vist_b.id, valor=4200,
        offset_dias=-30,
        endereco={"rua": "Av. Paulista", "numero": "1500", "bairro": "Bela Vista", "cidade": "São Paulo", "estado": "SP", "cep": "01310100", "latitude": -23.5614, "longitude": -46.6559},
        checklist_status="pendente_aceite", preencher_itens=True,
        problemas=[
            {"titulo": "Infiltração no teto", "prioridade": "urgente", "status": "aberto"},
            {"titulo": "Porta emperrada", "prioridade": "alta", "status": "aberto"},
        ],
    ))

    created.append(_create_imovel_com_contrato(
        db, codigo="IM-003", titulo="Studio Moema", tipo="Studio", tamanho="35m²",
        status_final="locado", locatario_id=loc_c.id, vistoriador_id=vist1.id, valor=1800,
        offset_dias=-60,
        endereco={"rua": "Rua Gaivota", "numero": "200", "bairro": "Moema", "cidade": "São Paulo", "estado": "SP", "cep": "04522000", "latitude": -23.6012, "longitude": -46.6643},
        checklist_status="aceito", preencher_itens=True,
    ))

    for codigo, titulo, tipo, tam in [
        ("IM-004", "Cobertura Vila Mariana", "Cobertura", "180m²"),
        ("IM-005", "Kitnet Consolação", "Kitnet", "28m²"),
    ]:
        im = Imovel(codigo=codigo, titulo=titulo, tipo=tipo, tamanho=tam, garagem=False, status="disponivel")
        db.add(im)
        db.flush()
        ensure_default_comodos(db, im.id)
        db.add(Endereco(
            imovel_id=im.id, rua=f"Rua {codigo}", numero="50",
            bairro="Vila Mariana", cidade="São Paulo", estado="SP", cep="04101000",
            latitude=-23.5890 + (0.01 * int(codigo[-1])),
            longitude=-46.6340 - (0.01 * int(codigo[-1])),
        ))

    im6 = Imovel(codigo="IM-006", titulo="Sala Comercial Pinheiros", tipo="Comercial", tamanho="90m²", status="em_vistoria")
    db.add(im6)
    db.flush()
    ensure_default_comodos(db, im6.id)
    db.add(Endereco(
        imovel_id=im6.id, rua="Rua dos Pinheiros", numero="800",
        bairro="Pinheiros", cidade="São Paulo", estado="SP", cep="05422000",
        latitude=-23.5675, longitude=-46.7033,
    ))

    log_operacao(db, admin.id, "seed", "sistema", None, "Dados de exemplo recriados")
    db.commit()

    return {
        "seeded": True,
        "message": "Dados recriados (usuários preservados)",
        "totals": {
            "usuarios": db.query(Usuario).count(),
            "imoveis": db.query(Imovel).count(),
            "contratos": db.query(Contrato).count(),
            "checklists": db.query(Checklist).count(),
            "problemas": db.query(Problema).count(),
            "itens_vistoria": db.query(ItemVistoria).count(),
        },
        "registros": created,
    }


def run_refresh_data(db: Session) -> dict:
    """Apaga imóveis, contratos, vistorias e problemas; mantém usuários."""
    admin = db.query(Usuario).filter(Usuario.email == "admin@onecheck.local").first()
    vist1 = db.query(Usuario).filter(Usuario.email == "vistoriador@onecheck.local").first()
    loc1 = db.query(Usuario).filter(Usuario.email == "locatario@onecheck.local").first()
    if not admin or not vist1 or not loc1:
        return {
            "seeded": False,
            "message": "Usuários mínimos ausentes (admin, vistoriador ou locatario).",
        }

    gestor = db.query(Usuario).filter(Usuario.email == "gestor@onecheck.local").first()
    vist2 = db.query(Usuario).filter(Usuario.email == "ana.vistoriadora@onecheck.local").first()
    loc2 = db.query(Usuario).filter(Usuario.email == "pedro.locatario@onecheck.local").first()
    loc3 = db.query(Usuario).filter(Usuario.email == "julia.locatario@onecheck.local").first()

    _clear_data_keep_users(db)
    return _populate_sample_data(
        db,
        admin=admin,
        gestor=gestor,
        vist1=vist1,
        vist2=vist2,
        loc1=loc1,
        loc2=loc2,
        loc3=loc3,
    )


def run_seed(db: Session, force: bool = False) -> dict:
    if db.query(Usuario).count() > 0 and not force:
        return {
            "seeded": False,
            "message": "Banco já possui dados. Use force=true, mode=expand ou mode=refresh_data.",
            "usuarios": db.query(Usuario).count(),
        }

    if force:
        _clear_all(db)

    credenciais: list[dict] = []
    admin = _novo_usuario("Administrador", "admin@onecheck.local", "admin", credenciais)
    gestor = _novo_usuario("Carlos Gestor", "gestor@onecheck.local", "gestor", credenciais)
    vist1 = _novo_usuario("João Vistoriador", "vistoriador@onecheck.local", "vistoriador", credenciais)
    vist2 = _novo_usuario("Ana Vistoriadora", "ana.vistoriadora@onecheck.local", "vistoriador", credenciais)
    loc1 = _novo_usuario("Maria Locatária", "locatario@onecheck.local", "locatario", credenciais)
    loc2 = _novo_usuario("Pedro Locatário", "pedro.locatario@onecheck.local", "locatario", credenciais)
    loc3 = _novo_usuario("Julia Locatária", "julia.locatario@onecheck.local", "locatario", credenciais)
    db.add_all([admin, gestor, vist1, vist2, loc1, loc2, loc3])
    db.flush()

    result = _populate_sample_data(
        db,
        admin=admin,
        gestor=gestor,
        vist1=vist1,
        vist2=vist2,
        loc1=loc1,
        loc2=loc2,
        loc3=loc3,
    )

    return {
        **result,
        "message": "Banco populado com dados completos",
        "usuarios": credenciais,
        **_info_mfa(),
    }


def run_expand(db: Session) -> dict:
    """Adiciona dados extras sem apagar existentes."""
    if db.query(Usuario).filter(Usuario.email == "ana.vistoriadora@onecheck.local").first():
        return {"seeded": False, "message": "Dados expandidos já existem (ana.vistoriadora@onecheck.local)."}

    credenciais: list[dict] = []
    vist2 = _novo_usuario("Ana Vistoriadora", "ana.vistoriadora@onecheck.local", "vistoriador", credenciais)
    loc2 = db.query(Usuario).filter(Usuario.email == "pedro.locatario@onecheck.local").first()
    loc3 = db.query(Usuario).filter(Usuario.email == "julia.locatario@onecheck.local").first()
    vist1 = db.query(Usuario).filter(Usuario.email == "vistoriador@onecheck.local").first()

    if not loc2:
        loc2 = _novo_usuario("Pedro Locatário", "pedro.locatario@onecheck.local", "locatario", credenciais)
        db.add(loc2)
    if not loc3:
        loc3 = _novo_usuario("Julia Locatária", "julia.locatario@onecheck.local", "locatario", credenciais)
        db.add(loc3)
    db.add(vist2)
    db.flush()

    for nome, cat in [("Torneiras", "hidraulica"), ("Box", "banheiro")]:
        if not db.query(ItemVistoria).filter(ItemVistoria.nome == nome).first():
            db.add(ItemVistoria(nome=nome, categoria=cat))
    db.flush()

    created = []
    if loc2 and vist1:
        created.append(_create_imovel_com_contrato(
            db, codigo="IM-002", titulo="Casa Jardim América", tipo="Casa", tamanho="120m²",
            status_final="locado", locatario_id=loc2.id, vistoriador_id=vist2.id, valor=4200,
            offset_dias=-30,
            endereco={"rua": "Av. Paulista", "numero": "1500", "bairro": "Bela Vista", "cidade": "São Paulo", "estado": "SP", "cep": "01310100", "latitude": -23.5614, "longitude": -46.6559},
            checklist_status="pendente_aceite", preencher_itens=True,
            problemas=[{"titulo": "Infiltração no teto", "prioridade": "urgente", "status": "aberto"}],
        ))

    if not db.query(Imovel).filter(Imovel.codigo == "IM-004").first():
        im = Imovel(codigo="IM-004", titulo="Cobertura Vila Mariana", tipo="Cobertura", tamanho="180m²", status="disponivel")
        db.add(im)
        db.flush()
        ensure_default_comodos(db, im.id)

    db.commit()
    return {
        "seeded": True,
        "message": "Dados expandidos adicionados",
        "registros": created,
        "usuarios": credenciais,
        "totals": {
            "usuarios": db.query(Usuario).count(),
            "imoveis": db.query(Imovel).count(),
            "contratos": db.query(Contrato).count(),
            "checklists": db.query(Checklist).count(),
            "problemas": db.query(Problema).count(),
        },
    }
