# DEBT-020 — Erros de autenticação, perfil e validação no mesmo envelope {sucesso, erro, erros}

> **Por que isso importa:** este registro junta, num lugar só, a prova de que o item seguiu o processo
> (branch, testes, segurança, documentação). O `scripts/dod_check.py <ID>` confere cada seção contra o
> git e o GitHub; a Sprint Review usa o mesmo arquivo.

- **Sprint:** 14 · **Issue:** #211 · **Branch:** `refactor/DEBT-020-erros-no-envelope` · **PR:** #<n>

## Entrega
Achado do DEBT-002. As regras de negócio respondiam no envelope (ADR-0003), mas os erros levantados pelo framework respondiam `{"detail": ...}`.

- **`app/erros.py`:** handlers globais para `HTTPException` e `RequestValidationError`.
  - Cobrem o 401 de token, o 403 de perfil, o 404 e o 405 do roteador, o 429 do limite de tentativas e o 422 de corpo, consulta ou caminho fora do schema.
  - O status e os cabeçalhos da exceção (`Retry-After`, `Allow`) não mudam.
  - No 422, `erros` traz a mensagem por campo (aninhado com ponto, `corpo` para JSON inválido ou corpo ausente), sem o prefixo "Value error, ", e `erro` é a primeira mensagem.
- **`app/limite_corpo.py`:** o 413 e o 400 de `Content-Length`, que o middleware responde direto, também usam o envelope.
- **OpenAPI:** `erros_no_openapi` aponta toda resposta 4xx e 5xx para `ErroResposta`, inclusive o 422 que o FastAPI acrescenta sozinho. Saem `DetalheErro` e `HTTPValidationError`.

| Critério de aceite | Prova |
|---|---|
| 401 de token, 403 de perfil e 422 de corpo fora do schema respondem `{sucesso: false, erro, erros}` com o mesmo status | `TestErrosDoFramework` (também 404, 405 com `Allow` e 429 com `Retry-After`), `TestLimiteDeCorpo` (413 e 400), `TestValidacaoDoCorpo` |
| O 422 de corpo fora do schema traz em `erros` a mensagem por campo | `test_422_traz_a_mensagem_por_campo`, `test_422_da_politica_de_senha_sem_o_prefixo_do_pydantic`, `test_422_de_parametro_de_consulta` |
| O OpenAPI deixa de declarar `DetalheErro` | `TestOpenapi::test_sem_os_formatos_antigos` e `test_todo_erro_documentado_e_o_envelope` (toda resposta 4xx e 5xx é `ErroResposta`) |
| Os testes que leem `detail` são atualizados com relatório e aprovação | Seção "Testes existentes alterados" |

## Testes
- **Novos:** 18 testes em `tests/integration/test_erros_no_envelope.py`. Os 13 escritos antes da mudança falhavam; os 5 de `TestCasosDosHandlers` (500 sem expor a exceção, 304 sem corpo, detalhe estruturado, mesmo nome na consulta e no corpo, JSON inválido) vieram da revisão e usam uma aplicação isolada só com os handlers. Cada um confere que não há `detail` e que o corpo valida contra `ErroResposta`, com `extra=forbid`.
- **Suíte completa:** 1432 passaram, 4 pulados, cobertura de branches em 97% (`app/erros.py` com 98%). Rodada por `scripts/testes_na_copia.sh`, sem o arquivo de segredos local.
- **Collection do Insomnia:** 166/166 contra a API da cópia (`scripts/rodar_collection.sh`, porta livre). Ela já lia `erro` antes de `detail`, então não muda.

## Segurança
- `/security-audit diff dev` em 2026-11-11: os 7 scanners com status `ok`. **Nenhum achado novo.** O arquivo local fora do git, os valores fictícios do teste de credenciais do seed e o DS026 do Dockerfile já existiam.
- **Ganho de confidencialidade:** o 422 padrão do FastAPI devolvia, em `detail[].input`, o valor recebido, inclusive uma senha fora da política. O envelope devolve só o nome do campo e a mensagem.
- `/code-review` (medium), com 10 apontamentos:
  - **Corrigidos:**
    - exceção não tratada responde `500` no envelope, com mensagem genérica, sem a exceção (o detalhe fica no log);
    - o mesmo nome de campo na consulta e no corpo não se sobrepõe;
    - `detail` estruturado vai para `erros`, e `204` e `304` saem sem corpo;
    - o prefixo "Assertion failed, " também sai das mensagens;
    - o OpenAPI é reescrito uma vez só, no schema em cache;
    - o limite de corpo usa o mesmo `corpo_de_erro`;
    - o relatório de testes alterados, preenchido antes do commit;
    - o registro deixa de citar arquivos fora do repositório.
  - **Sem mudança:**
    - os `except HTTPException` dos roteadores que já montam o envelope (`contratos.py`, `problemas.py`) continuam: a resposta deles já valida contra `ErroResposta`, e mexer neles sai dos critérios;
    - a chave `corpo` do JSON inválido: nenhum schema da API tem um campo `corpo`.
- A mudança não altera quem pode fazer o quê: o status, a ordem das checagens e as mensagens continuam os mesmos, e só o formato do corpo muda.

## Checklist antes da revisão
- [x] Campos que o perfil que ganha acesso passa a ver: nenhum perfil ganha acesso. O corpo de erro passa a ter menos dados (sai o `input` do 422).
- [-] Status finais: não se aplica, nenhuma regra de status muda.
- [x] Autorização antes de ler o corpo: os handlers só formatam a resposta, depois da exceção. A ordem das dependências não muda: o 401 e o 403 continuam antes da leitura do corpo, o que `test_seguranca_negacao_por_perfil.py` confere.
- [x] Login, refresh e tokens: o 401 do login, do MFA e do refresh já era envelope. O 401 de token ausente ou inválido muda só o corpo, e a mensagem é a mesma.
- [x] Perfis proibidos barrados antes da busca por ID: as dependências não mudam. Os 72 casos de `test_seguranca_negacao_por_perfil.py` continuam passando, agora lendo `erro`.

## Testes existentes alterados
O corpo dos erros do framework muda de `{"detail": ...}` para o envelope. As asserções mudam só a chave lida: a mensagem e o status conferidos são os mesmos. Nos testes parametrizados, uma linha vale para vários casos (72 casos em `test_perfil_proibido_recebe_403`).

| Arquivo :: teste | Antes | Depois | Por que precisa mudar | O comportamento atual quebra? |
|---|---|---|---|---|
| `tests/integration/test_contratos.py` :: `test_sem_autenticacao_retorna_401` de `TestCreateChecklist`, `TestCreateContrato`, `TestCreateProblema`, `TestListAgendamentos`, `TestListChecklists`, `TestListContratos` e `TestListProblemas` (7 testes) | `r.json()["detail"] == "Token ausente"` | `r.json()["erro"] == "Token ausente"` | o 401 de token passa ao envelope (critério 1) | Sim, de propósito: o corpo do 401 muda. Status e mensagem iguais |
| `tests/integration/test_contratos.py` :: `TestGetContrato::test_locatario_nao_acessa_contrato_alheio`, `TestCicloVidaContrato::test_locatario_nao_pode_encerrar_contrato` | `["detail"] ==` a mensagem de 403 | `["erro"] ==` a mesma mensagem | o 403 passa ao envelope | Sim, só o corpo |
| `tests/integration/test_checklists.py` :: `test_sem_autenticacao_retorna_401` de `TestAceitarChecklist`, `TestAddItem`, `TestDeleteFoto`, `TestGetChecklist`, `TestListItensVistoria`, `TestRejeitarChecklist`, `TestSubmeterChecklist`, `TestUpdateItem` e `TestUploadFoto` (9 testes) | `["detail"] == "Token ausente"` | `["erro"] == "Token ausente"` | o 401 de token passa ao envelope | Sim, só o corpo |
| `tests/integration/test_checklists.py` :: `TestAceitarChecklist::test_vistoriador_nao_pode_aceitar`, `TestRejeitarChecklist::test_vistoriador_nao_pode_rejeitar`, `TestAddItem::test_locatario_nao_pode_adicionar_item`, `TestSubmeterChecklist::test_gestor_nao_pode_submeter`, `TestDownloadPdf::test_locatario_alheio_recebe_403`, `TestDownloadPdf::test_vistoriador_nao_tem_acesso_ao_pdf_e_recebe_403` | `["detail"] ==` a mensagem de 403 | `["erro"] ==` a mesma mensagem | o 403 passa ao envelope | Sim, só o corpo |
| `tests/integration/test_seguranca_checklist_dono.py` :: `TestVerChecklist::test_locatario_de_outro_contrato_recebe_403_sem_dados`, `TestVerChecklist::test_outro_vistoriador_recebe_403_sem_dados`, `TestLocatarioDeOutroContratoNaoDecide::test_recebe_403_e_o_status_nao_muda`, `TestPdfDoChecklist::test_locatario_de_outro_contrato_recebe_403` | `corpo["detail"]` / `r.json()["detail"] ==` a mensagem | `["erro"] ==` a mesma mensagem | o 403 passa ao envelope | Sim, só o corpo. As asserções de "sem dados" continuam |
| `tests/integration/test_seguranca_negacao_por_perfil.py` :: `test_perfil_proibido_recebe_403` (72 casos), `test_gestor_nao_le_os_logs` | `["detail"] == "Permissão negada"` | `["erro"] == "Permissão negada"` | o 403 de perfil passa ao envelope | Sim, só o corpo. A conferência de que o banco não muda continua |
| `tests/integration/test_agendamentos_locatario.py` :: `test_locatario_nao_lista_os_de_outro_contrato` | `["detail"] ==` "Você não tem acesso a este contrato" | `["erro"] ==` a mesma | o 403 passa ao envelope | Sim, só o corpo |
| `tests/integration/test_historico_imovel.py` :: `test_locatario_sem_contrato_no_imovel_recebe_403` | `["detail"] ==` "Você não tem acesso a este imóvel" | `["erro"] ==` a mesma | o 403 passa ao envelope | Sim, só o corpo |
| `tests/integration/test_seguranca_mfa_setup_sessao_revogada.py` :: `TestSetupLoginComTokenAntigo::test_recusado_e_nenhum_segredo_pendente_gravado` | `["detail"] == "Token MFA inválido ou expirado"` | `["erro"] ==` a mesma | o 401 passa ao envelope | Sim, só o corpo. A conferência de que nenhum segredo é gravado continua |
| `tests/integration/test_seguranca_perfis_validos.py` :: `TestPerfilForaDaListaNaoAcessaNada::test_rota_autenticada_responde_401` (parametrizado) | `["detail"] == "Perfil de acesso inválido"` | `["erro"] ==` a mesma | o 401 passa ao envelope | Sim, só o corpo |
| `tests/integration/test_seguranca_senha_regras.py` :: `TestRotasDeSenha::test_mensagem_explica_a_regra` | `"pelo menos 10 caracteres" in r.json()["detail"][0]["msg"]` | `... in r.json()["erros"]["nova_senha"]` | o 422 de schema passa ao envelope, com a mensagem por campo (critério 2) | Sim, só o corpo. A asserção fica mais precisa: confere o campo |
| `tests/integration/test_openapi_respostas.py` :: `test_formatos_de_erro_estao_nos_componentes` | os componentes têm `ErroResposta` e `DetalheErro`, e o 401 é `anyOf` dos dois | os componentes têm `ErroResposta`, e o 401 aponta para ele | o OpenAPI deixa de declarar `DetalheErro` (critério 3) | Sim, de propósito: o OpenAPI muda |
| `tests/integration/test_openapi_respostas.py` :: `test_rotas_principais_declaram_envelope_e_erros` | cada erro declara `ErroResposta` e `DetalheErro`, ou o `HTTPValidationError` do FastAPI | cada erro declara `ErroResposta` | o 422 do FastAPI também passa ao envelope | Sim, só o OpenAPI. A asserção fica mais estrita |
| `tests/integration/test_openapi_respostas.py` :: `test_erros_seguem_um_dos_formatos_documentados` (2 dos 4 casos) e o import | o 401 sem token e o 422 de schema validados contra `DetalheErro` | validados contra `ErroResposta` | `DetalheErro` deixa de existir | Sim, só o corpo |

Nenhuma alteração enfraquece um teste: todo status e toda mensagem conferidos antes continuam conferidos, agora na chave do envelope. Duas ficam mais estritas: a política de senha confere o campo, e o OpenAPI exige só o envelope.

Aprovado por: Anderson em 2026-11-11

## Documentação
- ADR-0003: complemento do DEBT-020.
- `README.md`: o formato dos erros do framework e o 422 da política de senha.
- `app/respostas.py`: descrições dos erros no OpenAPI sem a menção a `detail`.
