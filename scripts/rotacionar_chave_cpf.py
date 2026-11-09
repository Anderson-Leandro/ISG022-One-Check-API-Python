"""Recifra os CPFs com a chave atual do CPF_CHAVES (SEC-031, ADR-0014).

Rotação, sem deixar nenhuma instância sem conseguir ler um CPF (o Render troca as instâncias aos poucos):
  1. CPF_CHAVES=<antiga>,<nova>   e faça o deploy: todas as instâncias passam a ler as duas.
  2. CPF_CHAVES=<nova>,<antiga>   e faça o deploy: os CPFs gravados daqui em diante usam a nova.
  3. python scripts/rotacionar_chave_cpf.py --aplicar   (com o mesmo CPF_CHAVES e o DATABASE_URL do banco)
  4. python scripts/rotacionar_chave_cpf.py             deve mostrar "0 com outra chave" e "0 ilegíveis";
     só então CPF_CHAVES=<nova> e deploy.

Uso:
    python scripts/rotacionar_chave_cpf.py            # só conta o que falta recifrar
    python scripts/rotacionar_chave_cpf.py --aplicar  # recifra
Sai com 1 se algum CPF não for decifrado por nenhuma chave (não tire chave nenhuma nesse caso).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cpf_cifrado import rotacionar
from app.database import engine


def main(aplicar: bool) -> int:
    with engine.begin() as conn:
        r = rotacionar(conn, aplicar=aplicar)
    verbo = "recifrados" if aplicar else "com outra chave (rode com --aplicar)"
    print(f"CPFs com a chave atual: {r['atual']}; {verbo}: {r['recifrados']}; ilegíveis: {len(r['ilegiveis'])}")
    for id_ in r["ilegiveis"]:
        print(f"  ilegível: usuário {id_}")
    return 1 if r["ilegiveis"] else 0


if __name__ == "__main__":
    sys.exit(main("--aplicar" in sys.argv[1:]))
