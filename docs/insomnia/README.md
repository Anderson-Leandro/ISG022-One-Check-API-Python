# Testes manuais com o Insomnia

> **Por que isso importa:** a suíte automatizada (`pytest`) roda a API em memória. Esta collection
> testa a API de verdade, no ar, pelo mesmo caminho que o front usa: HTTP, tokens reais, MFA, upload
> de arquivo e PDF. Serve para conferir uma correção à mão, demonstrar o controle de acesso ou
> investigar um bug.

- **Arquivo para importar:** [`onecheck-api.insomnia.json`](onecheck-api.insomnia.json), no formato de exportação v4.
- **Testado com:** Insomnia 12.5. As 168 requisições também foram rodadas contra a API local por um executor que reproduz os scripts, com todos os testes passando.
- **Conteúdo:** 168 requisições em 11 pastas, sendo 86 casos de sucesso (✅), 81 de falha (❌) e 1 de comportamento a revisar (⚠️).

## Como importar
1. No Insomnia: **Create → Import** (ou arraste o arquivo para a janela).
2. Escolha `docs/insomnia/onecheck-api.insomnia.json`.
3. Abra a collection **OneCheck API — testes manuais**.
4. No seletor de ambiente (canto superior esquerdo), escolha **Local (docker compose)**.

## Preparar o ambiente
Clique no ambiente e preencha as variáveis abaixo. As outras (tokens e IDs) ficam vazias: os scripts gravam essas sozinhos.

| Variável | O que colocar |
|---|---|
| `base_url` | `http://localhost:8000/api/v1` (já vem preenchido) |
| `senha_admin`, `senha_gestor`, `senha_vistoriador` | as senhas das contas do seed (ver abaixo) |
| `mfa_secret` | o "MFA secret" impresso pelo seed de desenvolvimento. Com ele, os scripts calculam o código TOTP sozinhos |
| `mfa_codigo` | alternativa ao `mfa_secret`: o código de 6 dígitos do app autenticador, digitado logo antes de rodar o login |
| `senha_teste` | a senha das contas que a collection cria (locatários e visualizador). Precisa ter pelo menos 10 caracteres e não pode ser óbvia, como `Insomnia.Teste#2026x` |
| `seed_secret` | opcional: o `SEED_SECRET` da API, para o teste da pasta 08 |

### Onde estão as senhas do seed
- **API em desenvolvimento** (`APP_ENV=development`): rode `python scripts/seed.py` num banco vazio. Ele imprime as senhas das contas `@onecheck.local` e o `MFA secret`, que é comum a admin, gestor e vistoriador.
- **Docker compose** (sobe em produção por padrão):
  - o primeiro carregamento é o `POST /api/v1/admin/seed` com o `SEED_SECRET`, que devolve as senhas **uma única vez**;
  - as contas com MFA configuram o autenticador no primeiro login, pela pasta **00a**.

Os segredos ficam só no ambiente do Insomnia, na sua máquina. **Não exporte a collection com o ambiente preenchido para o repositório.** O arquivo versionado tem todos os valores sensíveis vazios.

## Como rodar
Rode as pastas **na ordem**, porque cada uma prepara o que a próxima usa: tokens, usuários, imóvel, contrato, checklist. O mais prático é o **Collection Runner**: clique com o botão direito na collection ou numa pasta e escolha **Run**. O resultado de cada teste aparece na aba **Tests** de cada requisição.

| Pasta | O que faz | Grava no ambiente |
|---|---|---|
| 00 Saúde e autenticação básica | health, 404, rota protegida sem token, token malformado, login inválido | — |
| 00a Primeiro acesso (só quando o login pedir) | configura o MFA de admin, gestor e vistoriador; recusa reusar o token de setup (409) | `mfa_secret_<conta>`, tokens |
| 01 Login com MFA | login em duas etapas, token de verificação recusado no setup (401), refresh rotativo, reuso de refresh, MFA obrigatório | `token_admin`, `token_gestor`, `token_vistoriador`, IDs |
| 02 Usuários | cria locatário A, locatário B e visualizador (e-mail único por execução); perfil, listagem, escalada de privilégio | tokens e IDs dos três |
| 03 Imóveis | imóvel com endereço e coordenadas (sem geocoding), cômodos; acesso por perfil e por vínculo | `imovel_id`, `comodo_id` |
| 04 Contratos e agendamentos | contrato do locatário A, regras de datas e de imóvel locado, isolamento entre locatários | `contrato_id`, `agendamento_id` |
| 05 Checklists, fotos, aceite e PDF | vistoria inicial aceita e de encerramento rejeitada, upload de foto, travas depois do envio, separação de deveres, PDF | `checklist_id`, `foto_id`... |
| 06 Problemas e atualizações | problema do locatário A, status, linha do tempo, isolamento | `problema_id` |
| 07 Dashboard e logs | dashboard de cada perfil, logs com filtro, negação para locatário e visualizador | — |
| 08 Administração (seed) | só consultas: sem o segredo, com o segredo, sem token de admin | — |
| 09 Encerramento e limpeza | encerra o contrato, logout, desativa os usuários criados | — |

**Pasta 00a:** rode só se o login da pasta 01 responder `mfa_setup_required`. Contas que já têm o autenticador (como as do seed de desenvolvimento) respondem `mfa_required`, e a 00a falha nelas por isso.

### Uploads: selecione o arquivo uma vez
Quatro requisições da pasta 05 enviam arquivo. Depois de importar, abra cada uma e, no campo `foto` do corpo (Multipart), escolha o arquivo indicado na descrição:
- `docs/insomnia/fixtures/foto-valida.png`: "Vistoriador envia foto do item", "Locatário não envia foto" e "Foto em checklist já enviado".
- `docs/insomnia/fixtures/foto-invalida.jpg`: "Arquivo que não é imagem" (é texto com extensão `.jpg`).

O Insomnia guarda o caminho absoluto da sua máquina, e por isso o arquivo versionado vai com o campo vazio.

## Como ler os resultados
- **✅ / ❌** no nome mostra se o caso é de sucesso ou de falha. Num caso ❌, os testes passam quando a API **recusa** a operação.
- **Testes de cada requisição:**
  - o status HTTP;
  - o campo `sucesso` do envelope;
  - quando faz sentido, um trecho da mensagem de erro e o efeito esperado (status do checklist, dono do recurso).
- **Status dos erros:** todo erro responde com status de erro e o envelope `{"sucesso": false, "erro": ...}` ([ADR-0003](../adr/0003-status-http-dos-erros.md)). Os testes conferem os dois: o status exato e o campo `sucesso`.
- **Casos que a suíte automatizada ainda não cobre** estão marcados na descrição: SEC-032 (checklist de outro locatário) e SEC-033 (travas depois do envio). Ver [`docs/quality/avaliacao-testes-2026-11-02.md`](../quality/avaliacao-testes-2026-11-02.md).
- **⚠️** marca um comportamento atual que já está no backlog para mudar (SEC-020: filtro de data inválido ignorado).

## Cuidados
- **Limite de tentativas:**
  - cada execução completa gasta 1 código MFA errado do gestor e 3 logins falhos;
  - o limite é de 5 falhas por conta e 20 por IP em 15 minutos;
  - rodando mais de 4 ou 5 vezes seguidas, espere 15 minutos.
- **Não rode contra produção.** A suíte cria e altera dados: usuários, imóvel, contrato, vistorias, problemas. O ambiente **Outro servidor** vem vazio de propósito; use só com uma API de teste.
- **Dados que ficam:**
  - a pasta 09 desativa os usuários criados e encerra o contrato;
  - o imóvel, as vistorias e os problemas ficam no banco, com o código `INS-<número>`, para não apagar evidência;
  - num banco local descartável, isso não importa.

## Atualizar a collection
O JSON é gerado por [`gerar_collection.py`](gerar_collection.py). Para incluir ou mudar um caso, edite a lista `PASTAS` e rode:

```bash
python docs/insomnia/gerar_collection.py
```

Cada caso declara a rota, o perfil (token), o corpo, o status e a mensagem esperados, e o que gravar no ambiente. Os IDs das requisições são estáveis entre gerações: reimportar atualiza a collection sem duplicar.
