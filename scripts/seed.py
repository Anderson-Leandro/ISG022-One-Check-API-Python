"""Popula banco vazio com usuários, catálogo e dados de exemplo.

Em APP_ENV=development/test usa as credenciais fixas de demonstração. Fora disso
gera senhas aleatórias (exibidas só aqui) e os perfis com MFA configuram o
autenticador no primeiro login.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine
from app.seed_service import run_seed


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        result = run_seed(session)
    if not result.get("seeded"):
        print("Banco já possui dados. Seed ignorado.")
        return

    print("Seed concluído!")
    print("")
    print("Usuários (anote as senhas: não serão exibidas de novo):")
    for u in result["usuarios"]:
        print(f"  {u['email']} / {u['senha']}{' (MFA)' if u['mfa'] else ''}")
    print("")
    if "mfa_secret" in result:
        print(f"MFA secret (perfis com MFA): {result['mfa_secret']}")
        print(f"MFA código atual: {result['mfa_codigo_atual']}")
    else:
        print(result["mfa"])


if __name__ == "__main__":
    main()
