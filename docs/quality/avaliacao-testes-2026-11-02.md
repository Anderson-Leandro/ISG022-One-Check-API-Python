# Avaliação da suíte de testes — 2026-11-02

> **Por que isso importa:** cobertura de linhas diz quais linhas os testes *executam*, não se eles
> *detectam* um erro. Esta avaliação mede o que falta testar (ramos e combinações de perfil) e se os
> testes existentes falham quando o código está errado (mutação).

- **Item:** SPK-005 (#102), Sprint 12
- **Commit avaliado:** `089d100` (`dev`)
- **Suíte:** 824 testes, todos passando; 618 de integração e 206 unitários
- **Modo:** só leitura. Nenhum arquivo de código ou de teste foi alterado. As ferramentas rodaram fora do repositório (cópia do projeto e ambiente virtual separados).

## Resumo

| Técnica | Resultado | Leitura |
|---|---|---|
| Cobertura de linhas | 94,7% | alta, mas esconde ramos |
| Cobertura de ramos | **83,7%** (648 de 774 ramos) | 126 ramos nunca executados; alguns são checagens de segurança |
| Matriz de autorização | 6 rotas sem teste; **77 de 97** combinações "perfil proibido × rota" sem teste de negação; 13 rotas com ID sem o caso "não é dono" | é a principal lacuna |
| Mutação (`auth`, `deps`, `rate_limit`, checklists) | 581 mutantes, **96,6% mortos**; 20 sobreviventes, sendo 7 reais | os testes que existem são bons; faltam testes de negação |
| Revisão dos testes | 54 de 76 testes de negação em escrita não conferem se o banco ficou intacto; 1 teste com nome enganoso | melhorar a força das asserções |

**Achado mais importante:** a regra que impede um locatário de ler o checklist de outro contrato (`_assert_pode_ver_checklist`, `app/routers/checklists.py:91`) **não tem nenhum teste de negação**. Trocar o `and` por `or` nessa linha, o que deixaria qualquer locatário ler qualquer vistoria, não faz nenhum dos 824 testes falhar. O código atual está correto; o que falta é o teste que garante que continue assim.

## 1. Cobertura de ramos

Comando: `pytest --cov=app --cov-branch`.

| Módulo | Linhas | Ramos | Ramos faltando |
|---|---|---|---|
| `app/main.py` | 82,2% | 16,7% | 5 |
| `app/database.py` | 70,4% | 50,0% | 18 |
| `app/routers/agendamentos.py` | 83,9% | 65,0% | 7 |
| `app/routers/problemas.py` | 90,8% | 73,3% | 8 |
| `app/routers/imoveis.py` | 95,0% | 75,9% | 14 |
| `app/routers/checklists.py` | 92,0% | 78,3% | 23 |
| `app/rate_limit.py` | 96,5% | 78,6% | 3 |
| `app/uploads.py` | 95,7% | 80,0% | 2 |
| `app/seed_service.py` | 88,2% | 81,8% | 8 |
| `app/routers/contratos.py` | 93,1% | 86,6% | 15 |
| `app/routers/auth_router.py` | 96,6% | 88,0% | 6 |
| demais módulos | — | 85% a 100% | 17 |
| `auth.py`, `deps.py`, `auditoria.py`, `cpf.py`, `senhas.py`, `cabecalhos.py` | 100% | 100% | 0 |

### Ramos sem teste que importam para segurança
| Local | O que nunca é testado | Risco |
|---|---|---|
| `checklists.py:89-93` (`_assert_pode_ver_checklist`) | o 403 para locatário de outro contrato e para vistoriador de outro checklist | BOLA/IDOR na leitura de vistoria (R-001) |
| `checklists.py:73-75` (`_assert_pode_aceitar`) | o 403 para quem não é admin, gestor nem o locatário dono | aceite de laudo por terceiro (R-003) |
| `checklists.py:241`, `:301` | upload e exclusão de foto em checklist que já saiu de `em_preenchimento` | alterar evidência depois do envio (R-003) |
| `checklists.py:366` | `enviar-para-aceite` com checklist fora de `em_preenchimento` | máquina de estados |
| `contratos.py:272` | listagem de checklists de um contrato pelo vistoriador (filtro "só os seus") | vistoriador ver vistorias de outros |
| `auth_router.py:128-131`, `:151-154` | token de setup de MFA de sessão já revogada (`sessao_vigente`) | sessão revogada continuar configurando MFA |
| `rate_limit.py:48-51` | descarte de chaves expiradas quando passam de 10.000 | memória do limitador sob varredura de e-mails |
| `checklists.py:265`, `contratos.py:381`, `problemas.py:115` | foto maior que `MAX_UPLOAD_MB` dentro do handler | defesa em profundidade; o `LimiteCorpoMiddleware` corta antes |
| `contratos.py:169`, `:231` | cancelar contrato não ativo; agendar em contrato não ativo | regra de negócio |

Os demais ramos faltando são, em sua maioria, respostas "não encontrado" (404 ou `sucesso: false`) e caminhos de infraestrutura (`database.py` com PostgreSQL, `main.py` na inicialização).

## 2. Matriz de autorização

**Método:** em vez de inferir pelos nomes dos testes, um plugin de pytest (fora do repositório) registrou cada requisição feita pela suíte: rota, perfil do token, status HTTP e, como a API responde vários erros com HTTP 200 e `sucesso: false`, também o corpo. Foram 801 requisições de 552 testes, cruzadas com as 82 rotas do OpenAPI e com a proteção de cada uma (`feature_map.py`).

**Legenda:** `P` permitido (2xx com sucesso) · `N` negado (401/403 ou falha "sem permissão") · `4` 404 · `V` validação (400/409/413/422/429) · `F` falha de negócio com 200 · `·` nenhum teste com esse perfil.

### Lacunas
- **Rotas sem nenhum teste (6):**
  - `PATCH /imoveis/{id}/endereco`;
  - `POST /contratos/{id}/encerrar` e `POST /contratos/{id}/cancelar` (as versões `PATCH` têm teste);
  - `GET /checklists/{id}/pdf` e `GET /checklists/{id}/download-pdf` (só `/download` tem teste);
  - `GET /`.
- **Negação por perfil nas 32 rotas restritas a perfis (`require_roles`):**
  - 77 das 97 combinações "perfil proibido × rota" nunca são testadas, e 18 dessas rotas não têm nenhum teste de negação;
  - os perfis mais esquecidos são o visualizador (30 combinações), o vistoriador (25) e o locatário (21);
  - a checagem é declarativa (a mesma dependência em todas as rotas), o que reduz o risco. Mesmo assim, uma rota que perca a dependência numa refatoração não é detectada.
- **Rotas com ID sem o caso "não é o dono" (13):** todas as rotas de checklist por ID (`GET`, itens, fotos, submeter, aceitar e rejeitar pelo locatário, PDF), além de `GET /contratos/{id}/checklists` e `POST /contratos/{id}/problemas` para o vistoriador e `GET /imoveis/{id}/endereco` para o locatário.
- **Acesso anônimo:** 37 das 74 rotas protegidas não têm teste de requisição sem token (401). O risco é baixo: o `get_current_user` é comum a todas e tem 100% de cobertura.

### Matriz completa
| Rota | Proteção | Testes | anon | admin | gestor | vistoriador | locatário | visualizador |
|---|---|---|---|---|---|---|---|---|
| `GET /health` | public | 3 | P | · | · | · | · | · |
| `GET /uploads/{filename}` | public | 7 | 4P | · | · | · | · | · |
| `POST /auth/login` | public | 44 | FPV | · | · | · | · | · |
| `POST /auth/mfa/verify` | public | 14 | FPV | · | · | · | · | · |
| `GET /auth/mfa/setup-login` | public | 10 | NPV | · | · | · | · | · |
| `POST /auth/mfa/activate-login` | public | 8 | FPV | · | · | · | · | · |
| `GET /auth/mfa/setup` | auth | 3 | · | P | · | · | P | · |
| `POST /auth/mfa/setup` | auth | 9 | · | P | · | · | P | · |
| `POST /auth/mfa/activate` | auth | 10 | · | FPV | · | · | P | · |
| `POST /auth/mfa/disable` | role (admin) | 4 | · | NP | · | · | · | · |
| `POST /auth/mfa/habilitar` | auth | 1 | · | · | · | · | P | · |
| `POST /auth/mfa/desabilitar` | auth | 12 | · | N | N | N | FPV | · |
| `POST /auth/refresh` | public | 21 | FP | · | · | · | · | · |
| `POST /auth/logout` | auth | 5 | N | · | · | · | P | · |
| `GET /usuarios/me` | auth | 25 | N | NP | · | NP | NP | P |
| `PATCH /usuarios/me` | auth | 10 | N | · | · | · | FPV | · |
| `PUT /usuarios/me/senha` | auth | 8 | · | · | · | · | FPV | · |
| `POST /usuarios/me/mfa/setup` | auth | 2 | N | · | · | · | P | · |
| `POST /usuarios/me/mfa/enable` | auth | 8 | N | FP | · | · | FP | · |
| `DELETE /usuarios/me/mfa` | auth | 12 | N | N | N | N | FPV | · |
| `GET /usuarios` | role (admin, gestor) | 13 | N | P | P | N | N | N |
| `POST /usuarios` | role (admin, gestor) | 17 | N | FPV | NP | · | N | · |
| `GET /usuarios/{usuario_id}` | role (admin, gestor) | 6 | N | FP | P | · | N | · |
| `PUT /usuarios/{usuario_id}` | role (admin, gestor) | 28 | · | FNPV | NP | N | · | · |
| `DELETE /usuarios/{usuario_id}` | role (admin, gestor) | 6 | · | FP | N | · | N | · |
| `POST /usuarios/{usuario_id}/mfa/habilitar` | role (admin, gestor) | 3 | · | PV | · | · | · | · |
| `POST /usuarios/{usuario_id}/mfa/enable` | role (admin, gestor) | 5 | · | FPV | N | · | · | · |
| `POST /usuarios/{usuario_id}/mfa/desabilitar` | role (admin, gestor) | 4 | · | P | N | · | · | · |
| `DELETE /usuarios/{usuario_id}/mfa` | role (admin, gestor) | 8 | · | NP | N | · | N | · |
| `GET /imoveis` | auth | 7 | N | P | · | P | P | · |
| `POST /imoveis` | role (admin, gestor) | 5 | N | P | · | · | · | · |
| `GET /imoveis/{imovel_id}` | auth | 11 | N | FP | P | NP | NP | P |
| `PUT /imoveis/{imovel_id}` | role (admin, gestor) | 7 | N | FP | · | · | · | · |
| `DELETE /imoveis/{imovel_id}` | role (admin, gestor) | 3 | · | FP | · | · | · | · |
| `GET /imoveis/{imovel_id}/endereco` | auth | 9 | N | FP | P | NP | · | P |
| `PATCH /imoveis/{imovel_id}/endereco` | role (admin, gestor) | 0 | · | · | · | · | · | · |
| `PUT /imoveis/{imovel_id}/endereco` | role (admin, gestor) | 1 | · | P | · | · | · | · |
| `POST /imoveis/{imovel_id}/endereco` | role (admin, gestor) | 5 | N | FP | · | · | · | · |
| `GET /imoveis/{imovel_id}/comodos` | auth | 12 | N | P | P | NP | NP | P |
| `POST /imoveis/{imovel_id}/comodos` | role (admin, gestor) | 1 | · | P | · | · | · | · |
| `PUT /imoveis/{imovel_id}/comodos/{comodo_id}` | role (admin, gestor) | 1 | · | P | · | · | · | · |
| `DELETE /imoveis/{imovel_id}/comodos/{comodo_id}` | role (admin, gestor) | 1 | · | P | · | · | · | · |
| `GET /contratos` | auth | 7 | N | P | · | P | P | · |
| `POST /contratos` | role (admin, gestor) | 10 | N | FP | · | · | · | · |
| `GET /contratos/{contrato_id}` | auth | 13 | · | FP | P | NP | NP | P |
| `POST /contratos/{contrato_id}/encerrar` | role (admin, gestor) | 0 | · | · | · | · | · | · |
| `PATCH /contratos/{contrato_id}/encerrar` | role (admin, gestor) | 3 | · | FP | · | · | N | · |
| `POST /contratos/{contrato_id}/cancelar` | role (admin, gestor) | 0 | · | · | · | · | · | · |
| `PATCH /contratos/{contrato_id}/cancelar` | role (admin, gestor) | 1 | · | P | · | · | · | · |
| `GET /contratos/{contrato_id}/agendamentos` | auth | 12 | N | FP | P | NP | N | P |
| `POST /contratos/{contrato_id}/agendamentos` | role (admin, gestor) | 6 | · | FP | · | N | N | · |
| `GET /contratos/{contrato_id}/checklists` | auth | 5 | N | FP | · | · | NP | · |
| `POST /contratos/{contrato_id}/checklists` | role (admin, gestor) | 16 | N | FP | P | N | N | N |
| `POST /contratos/{contrato_id}/problemas` | auth | 46 | N | 4PV | · | · | 4NPV | · |
| `GET /contratos/{contrato_id}/problemas` | auth | 12 | N | 4P | P | N | NP | N |
| `PUT /agendamentos/{agendamento_id}` | role (admin, gestor) | 3 | · | FP | · | N | · | · |
| `DELETE /agendamentos/{agendamento_id}` | role (admin, gestor) | 3 | · | FP | · | N | · | · |
| `GET /itens-vistoria` | auth | 3 | N | P | · | · | · | · |
| `GET /checklists/{checklist_id}` | auth | 6 | N | FP | · | P | P | P |
| `POST /checklists/{checklist_id}/itens` | auth | 8 | N | FP | · | FP | N | · |
| `PUT /checklists/{checklist_id}/itens/{item_id}` | auth | 6 | N | · | · | FP | · | · |
| `POST /checklists/{checklist_id}/itens/{item_id}/fotos` | auth | 17 | N | · | · | FPV | · | · |
| `DELETE /checklists/{checklist_id}/itens/{item_id}/fotos/{foto_id}` | auth | 3 | N | · | · | FP | · | · |
| `PATCH /checklists/{checklist_id}/submeter` | auth | 13 | N | F | N | FP | · | · |
| `PATCH /checklists/{checklist_id}/enviar-para-aceite` | role (admin, gestor) | 4 | · | FP | · | · | · | · |
| `PATCH /checklists/{checklist_id}/aceitar` | auth | 8 | N | FP | NP | N | P | · |
| `PATCH /checklists/{checklist_id}/rejeitar` | auth | 6 | N | FP | N | N | P | · |
| `GET /checklists/{checklist_id}/pdf` | auth | 0 | · | · | · | · | · | · |
| `GET /checklists/{checklist_id}/download-pdf` | auth | 0 | · | · | · | · | · | · |
| `GET /checklists/{checklist_id}/download` | auth | 4 | · | P | · | N | NP | · |
| `GET /problemas/{problema_id}` | auth | 14 | · | 4P | P | N | NP | N |
| `PATCH /problemas/{problema_id}/status` | role (admin, gestor) | 3 | · | PV | · | · | N | · |
| `POST /problemas/{problema_id}/atualizacoes` | role (admin, gestor) | 15 | · | PV | · | N | N | · |
| `GET /problemas/{problema_id}/atualizacoes` | auth | 12 | · | P | P | N | NP | N |
| `GET /dashboard` | auth | 12 | N | P | P | P | P | P |
| `GET /logs` | role (admin, gestor) | 10 | N | P | · | · | N | · |
| `GET /admin/data/status` | auth | 5 | NP | P | · | · | · | · |
| `PATCH /admin/refresh-data` | auth | 1 | F | · | · | · | · | · |
| `PUT /admin/refresh-data` | auth | 1 | F | · | · | · | · | · |
| `POST /admin/refresh-data` | auth | 5 | FN | N | · | · | · | · |
| `POST /admin/seed` | auth | 22 | 4FNP | NP | N | · | · | · |
| `GET /` | public | 0 | · | · | · | · | · | · |

`GET /logs` com o gestor não tem nenhum teste, embora o gestor tenha acesso. Esse é justamente o comportamento questionado no SEC-018.

## 3. Testes de mutação

**Ferramenta:** mutmut 3.3.1, numa cópia do projeto.

**Módulos mutados:** `app/auth.py`, `app/deps.py`, `app/rate_limit.py` e `app/routers/checklists.py`.

**Testes excluídos da mutação:** os 4 arquivos que sobem o app num subprocesso (`test_seguranca_cabecalhos_http.py`, `test_config_segredos.py`, `test_seed_inicializacao.py` e `test_seguranca_infra.py`). Eles são incompatíveis com a instrumentação do mutmut e testam configuração de produção, que está fora desses módulos.

| Módulo | Mutantes | Mortos | Sobreviventes | Reais |
|---|---|---|---|---|
| `app/auth.py` | 252 | 252 (100%) | 0 | 0 |
| `app/deps.py` | 174 | 162 (93,1%) | 12 | 4 |
| `app/rate_limit.py` | 72 | 71 (98,6%) | 1 | 0 |
| `app/routers/checklists.py` | 83 | 76 (91,6%) | 7 | 7 |
| **Total** | **581** | **561 (96,6%)** | **20** | **11** |

### Sobreviventes
| Mutante | Real? | O que significa |
|---|---|---|
| `checklists._assert_pode_ver_checklist`: `contrato and ...` → `contrato or ...` | **sim, grave** | qualquer locatário leria qualquer checklist e nenhum teste falha |
| `checklists._assert_pode_ver_checklist`: gestor removido da lista de perfis permitidos | **sim** | nenhum teste confere que o gestor lê um checklist por ID |
| `checklists._assert_pode_aceitar` e `_assert_pode_ver_checklist`: 403 → 404 ou sem status | sim, baixo | os testes dessas negações não existem ou não conferem o status exato |
| `deps.assert_acesso_contrato`, `require_roles`, checklists: mensagem de erro alterada ou removida | sim, baixo | os testes não conferem a mensagem (`detail`) |
| `deps.require_roles`: condição invertida (4 mutantes) | **não** | `require_roles` roda na importação, antes de o mutmut ativar o mutante. Aplicadas à mão, as mesmas mutações fazem a suíte falhar na hora |
| `rate_limit.LimitadorTentativas.__init__`: `janela_s = None` | **não** | o limitador é criado na importação, então vale a mesma limitação |

### Limitação importante
O mutmut 3 **não muta funções com decorador**, e por isso não mutou nenhum handler de rota (`@router.get`, `@router.post`...). Em `checklists.py`, só as funções auxiliares de autorização foram mutadas. A máquina de estados dos checklists e as travas de edição, que ficam dentro dos handlers, não foram medidas por mutação; para elas vale a análise de ramos da seção 1. Medir os handlers exigiria outra ferramenta, como o cosmic-ray, ou mover as regras para funções sem decorador.

## 4. Revisão dos testes

Feita por uma varredura da árvore sintática dos testes e conferida por leitura.

- **Testes de negação em escrita:** de 76 testes que esperam negação (401/403) em POST/PUT/PATCH/DELETE, **54 não conferem depois** se o recurso ficou intacto. Exemplos:
  - `test_gestor_nao_promove_outro_a_perfil_*` confere o 403, mas não relê o perfil no banco;
  - `test_locatario_nao_pode_alterar_status_e_recebe_*`;
  - `test_vistoriador_nao_pode_excluir_nem_atualizar`.

  Um 403 devolvido *depois* de gravar passaria nesses testes.
- **Testes que só conferem o status ou o campo `sucesso`:** 179 de 719. Em testes de negação isso costuma bastar. Em testes do caminho feliz, falta conferir o corpo e o efeito; as maiores proporções estão em `test_seguranca_limite_corpo.py` (7 de 10), `test_seguranca_rate_limit.py` (8 de 13) e `test_problemas.py` (13 de 23).
- **Nome enganoso:** `test_checklists.py::TestSubmeterChecklist::test_outro_vistoriador_nao_pode_submeter` usa o token do **gestor**, não de um segundo vistoriador. O caso "outro vistoriador" continua sem teste.
- **Falsos positivos descartados:** 7 testes sem `assert`. Dois usam um helper que faz as verificações (`_confere`) e cinco testam que o schema aceita um valor válido, ou seja, passam se não houver exceção.

## Lacunas → backlog
| Item | Prioridade | Cobre |
|---|---|---|
| **SEC-032** Testes de negação de acesso aos checklists por quem não é dono | must | seção 1 (`checklists.py:73-93`), seção 2 (13 rotas), mutantes reais de checklists |
| **SEC-033** Testes das travas do checklist depois do envio | should | `checklists.py:241`, `:301`, `:366` |
| **SEC-034** Testes de sessão revogada no setup de MFA e do teto de chaves do limitador | could | `auth_router.py:128-154`, `rate_limit.py:48-51` |
| **DEBT-011** Testes de negação por perfil em todas as rotas restritas | should | 77 combinações e as 6 rotas sem teste |
| **DEBT-012** Negações em escrita conferem o estado e o status exato | should | 54 testes da seção 4 e o teste com nome enganoso |
| **DEBT-010** (refinado) | could | os ramos 404 e de validação restantes, mais `database.py` e `main.py` |

## Como repetir
1. **Cobertura de ramos:** `pytest --cov=app --cov-branch --cov-report=term-missing`.
2. **Matriz:** um plugin de pytest que envolve o app ASGI e grava `(teste, método, rota, perfil, status, sucesso)` por requisição, cruzado com `app.openapi()` e `feature_map.py`. Não fica versionado; vale versionar em `tests/tools/` se o time quiser repetir a cada sprint (decisão a tomar).
3. **Mutação:**
   - copie o projeto com `git archive`;
   - em `setup.cfg`, use `paths_to_mutate=app/` e liste em `do_not_mutate` os módulos fora do escopo;
   - em `pytest.ini`, ignore os testes que sobem subprocesso;
   - rode `mutmut run --max-children 4` (uns 2 minutos para 581 mutantes).
