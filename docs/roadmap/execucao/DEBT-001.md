# DEBT-001 — Modelos Pydantic nos corpos das rotas de problemas

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 13 · **Issue:** #77 · **Branch:** `refactor/DEBT-001-corpos-problemas-openapi` · **PR:** #203

## Entrega
- As três rotas leem o corpo à mão. As de criação aceitam JSON ou multipart com a foto, e todas autorizam antes de ler o corpo (assim quem não pode agir não chega a enviar arquivo). Por isso o OpenAPI não mostrava o corpo.
- Os modelos de `app/schemas.py` passam a documentá-lo pelo `openapi_extra`, com a função `corpo_no_openapi`, o mesmo caminho que a rota de fotos do checklist já usava. A leitura, as validações e as mensagens de erro não mudam.
  - `ProblemaCreate` (JSON) e `ProblemaForm` (multipart, com `foto` binária), em `POST /contratos/{id}/problemas`;
  - `ProblemaStatusUpdate`, em `PATCH /problemas/{id}/status`;
  - `AtualizacaoProblemaCreate` (JSON) e `AtualizacaoProblemaForm` (multipart), em `POST /problemas/{id}/atualizacoes`.
- As prioridades e os status aceitos viram constantes (`PRIORIDADES_PROBLEMA`, `STATUS_PROBLEMA`), usadas pelas rotas e pelo `enum` do OpenAPI. Assim o que a documentação lista e o que a API aceita não se separam, como no DEBT-016. Na criação, o `status` documentado é só `aberto`, a regra que a rota já aplica. Os status finais (`STATUS_PROBLEMA_ENCERRADOS`) ficam junto dos outros.
- Correção encontrada na revisão: um corpo JSON que não é objeto (`null`, `[]`, um número) ou um `status` que não é texto davam erro 500 nas três rotas. Agora dão o mesmo `422` de campo ausente.

| Critério de aceite | Prova |
|---|---|
| As três rotas aparecem no OpenAPI com `requestBody` | `test_criar_problema_em_json_e_multipart`, `test_mudar_status_em_json_com_os_status_aceitos`, `test_atualizacao_em_json_e_multipart` (campos obrigatórios, `enum`, `foto` binária no multipart, `foto_url` só no JSON) |
| Os testes existentes continuam passando | suíte completa sem nenhum teste existente alterado; e os valores documentados são aceitos (`test_cada_status_documentado_e_aceito`, `test_cada_prioridade_documentada_e_aceita`), e um status fora deles continua `422` com a mensagem de campo, sem gravar |

## Testes
- **Novos:** 22 testes em `tests/integration/test_openapi_corpos_problemas.py`; antes da mudança, os do OpenAPI falhavam (sem `requestBody`) e os de corpo fora do formato davam erro 500.
- **Suíte completa:** 1243 passaram, 3 pulados, cobertura 96%. Rodada numa cópia sem o arquivo de segredos local.
- **Collection do Insomnia:** não muda, porque nenhuma resposta muda.

## Segurança
- `/security-audit diff dev` em 2026-11-08: os 7 scanners com status `ok`. **Nenhum achado novo.** Os do gitleaks são o arquivo local fora do git e os valores fictícios do teste de credenciais do seed; o DS026 do Dockerfile já existia.
- Mantém a autorização antes da leitura do corpo (o motivo de as rotas não usarem os modelos como parâmetro, que faria o FastAPI ler o corpo antes das checagens).
- Documentação do contrato (OWASP API9:2023, inventário): os campos e os valores aceitos ficam explícitos.
- `/code-review` (medium), com 10 apontamentos:
  - **Corrigidos:**
    - o erro 500 com corpo fora do formato, nas três rotas;
    - os modelos JSON e multipart passam a herdar de uma base comum;
    - os status finais junto dos outros;
    - o mínimo de 5 caracteres publicado como `minLength`;
    - a função recusa um modelo aninhado, cujas referências não resolveriam no OpenAPI.
  - **Sem mudança:**
    - a rota de fotos do checklist, só multipart, continua com o corpo escrito à mão, fora do critério;
    - o modelo não valida o `enum` em tempo de execução, porque a validação e a mensagem continuam na rota, e o teste de `ProblemaCreate` que já existia aceita outros valores;
    - o apontamento sobre o registro, que estava desatualizado.

## Checklist antes da revisão
- [-] Campos que o perfil que ganha acesso passa a ver: nenhum perfil ganha acesso; só o OpenAPI muda.
- [x] Status finais: o `enum` do PATCH lista os 5 status que a rota aceita, inclusive os dois finais (`resolvido`, `fechado`).
- [x] Autorização antes de ler o corpo: mantida de propósito. Os modelos só documentam e não viram parâmetro da rota.
- [-] Login, refresh e tokens: não se aplica.
- [-] Perfis proibidos barrados antes da busca por ID: não muda; a ordem das checagens é a mesma.

## Testes existentes alterados
Nenhum.

## Documentação
- O próprio OpenAPI (`/docs`, `/openapi.json`) passa a mostrar os corpos.
- Nada no README: o mapa de rotas não detalha os campos.
