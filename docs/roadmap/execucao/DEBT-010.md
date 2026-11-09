# DEBT-010 — Cobrir os ramos não testados de agendamentos, geocoding e database

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #86 · **Branch:** `test/DEBT-010-cobertura-ramos` · **PR:** #<n>

## Entrega
Só testes, sem mudar o código de produção. Os ramos que faltavam, apontados pela avaliação do SPK-005 (`docs/quality/avaliacao-testes-2026-11-02.md`), passam a ter teste que confere a resposta:
- **`tests/integration/test_ramos_rotas.py` (51 testes):**
  - os "não encontrado" de agendamentos, problemas, contratos, imóveis e cômodos, cada um com a mensagem;
  - um problema de contrato excluído responde com o 404 do contrato;
  - corpo que não é JSON, data em formato inválido, foto grande demais e `foto_url` de fora, todos com 422 e sem gravar;
  - os ramos de campos opcionais: só a observação, só o tipo, multipart sem foto, endereço com e sem coordenadas, endereço criado na alteração do imóvel;
  - o `_parse_datetime` de agendamentos e contratos.
- **`tests/unit/test_database_migracoes.py` (5 testes):** um SQLite temporário com as tabelas de antes ganha cada coluna nova na inicialização. Os dados ficam, o CPF é cifrado (SEC-031) e o texto do login falho sai (SEC-019); a segunda execução não muda nada.

| Critério de aceite | Prova |
|---|---|
| Cobertura de ramos (`pytest --cov-branch`) de agendamentos, imóveis, problemas e contratos em pelo menos 90% | agendamentos 100% (20/20), contratos 96,8% (122/126), imóveis 96,1% (73/76), problemas 93,2% (41/44); antes: 70%, 88,9%, 80,3% e 77,3% |
| Os ramos de "não encontrado" do relatório têm teste que confere a resposta | `_nao_encontrado` confere o status 404 e a mensagem em cada rota: `TestAgendamentos`, `TestProblemas`, `TestContratos`, `TestImoveis` |
| A cobertura de ramos total sobe de 83,7% para pelo menos 90% | **92,3%** (857/928 ramos). Antes deste item, 86,6%; 83,7% era a medida do SPK-005 |

## Testes
- **Novos:** 56 testes (51 + 5), listados acima.
- **Suíte completa:** 1372 passaram, 4 pulados. Cobertura de linhas e ramos combinada em 97%; só de ramos, 92,3%. Rodada numa cópia sem o arquivo de segredos local.
- `database.py` passa de 50% para 82,1% de ramos. Os que restam são os do PostgreSQL e do MySQL (o alargamento do CPF, que roda no CI com o PostgreSQL) e o `geocoding` está em 90%.

## Segurança
- `/security-audit diff dev` em 2026-11-09: os 7 scanners com status `ok`. **Nenhum achado novo.**
- Item só de testes; nenhuma superfície da API muda. Os ramos de segurança já tinham saído para SEC-032, SEC-033 e SEC-034.
- `/code-review` (medium), com 10 apontamentos:
  - **Virou o BUG-002, fora da sprint:** um defeito real nas rotas. Num multipart, a foto é gravada antes das validações seguintes, e um pedido recusado depois (404, 409 ou 422) deixa o arquivo órfão no disco (CWE-400). O item é só de testes, então a correção ficou para um item próprio.
  - **Corrigidos nos testes:**
    - a conferência de que o banco não mudou em todas as escritas recusadas;
    - o CPF migrado decifrado e comparado com o original;
    - a segunda execução da migração conferida também nos dados (o CPF não é cifrado duas vezes);
    - a limpeza do SEC-019 com linhas que precisam ficar;
    - o 422 do corpo inválido conferido pelo campo;
    - os status exatos do endereço;
    - a repetição dos argumentos e um `delete` sem efeito.
  - **Sem mudança:** derivar a lista de colunas migradas do `Base.metadata` não funciona, porque as tabelas antigas mínimas não têm as outras colunas do modelo, que não passam por migração.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: não se aplica, nenhuma rota muda.
- [-] Status finais: não se aplica, nenhuma regra muda.
- [-] Autorização antes de ler o corpo: não se aplica, nenhuma rota muda.
- [-] Login, refresh e tokens: não se aplica.
- [-] Perfis proibidos barrados antes da busca por ID: não se aplica, nenhuma rota muda.

## Testes existentes alterados
Nenhum.

## Documentação
- Nada a atualizar: o item só acrescenta testes.
- Backlog: BUG-002 (novo, fora da sprint).
