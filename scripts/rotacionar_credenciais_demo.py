"""Substitui as credenciais de demonstração publicadas no repositório.

Contas criadas pelo seed antigo usam senhas e segredo TOTP que estão no código.
Para cada conta ativa nessa situação: gera nova senha, reseta o MFA (perfis
obrigatórios configuram o autenticador no próximo login) e revoga os refresh tokens.

Uso (aponte DATABASE_URL para o banco a corrigir):
    python scripts/rotacionar_credenciais_demo.py           # só lista as contas expostas
    python scripts/rotacionar_credenciais_demo.py --aplicar # troca as credenciais
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.seed_service import contas_com_credenciais_publicas, rotacionar_credenciais_publicas


def main(aplicar: bool) -> int:
    with SessionLocal() as session:
        expostas = contas_com_credenciais_publicas(session)
        if not expostas:
            print("Nenhuma conta ativa usa credenciais de demonstração.")
            return 0
        if not aplicar:
            print("Contas com credenciais públicas (rode com --aplicar para trocar):")
            for user in expostas:
                print(f"  {user.email} ({user.role})")
            return 1
        print("Novas credenciais (anote: não serão exibidas de novo):")
        for c in rotacionar_credenciais_publicas(session):
            print(f"  {c['email']} / {c['senha']}{' (configurar MFA no próximo login)' if c['mfa'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--aplicar" in sys.argv[1:]))
