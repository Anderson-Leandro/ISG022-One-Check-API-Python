# Acordo de Trabalho — OneCheck API

> **Por que isso importa:** regras combinadas antes evitam discussão depois. Num time, o acordo
> garante que todos entendem "pronto" da mesma forma.

## Papéis
| Papel | Quem | Responsabilidade |
|---|---|---|
| Product Owner (PO/PM) | Gabriel Henrique Santana | visão, prioridade do backlog, critérios de aceite, aceite na review |
| Tech Lead (TL) | Anderson Mendes Leandro | arquitetura, padrões, ADRs, qualidade técnica, revisão |
| Dev | Ismael Alves de Almeida | implementar, testar, documentar, revisar |
| Dev | Luiz Felipe dos Santos | implementar, testar, documentar, revisar |

Por enquanto, Anderson Mendes Leandro é o responsável por todos os itens do backlog e por todos os riscos; a distribuição entre o time acontece no planejamento de cada sprint.

## Cadência (Scrum, sprint de 14 dias)
- **Planning** (início): Sprint Goal + itens `ready` dentro da capacidade.
- **Acompanhamento** (diário ou por sessão de trabalho): andamento, impedimentos, decisões.
- **Refinamento** (meio da sprint): preparar itens da próxima sprint até a DoR.
- **Review** (fim): demonstrar o incremento e as evidências.
- **Retrospectiva** (fim): 1 coisa que funcionou, 1 melhoria → vira ação no backlog.

## Contexto deste projeto
- **Time de quatro pessoas:** o PO prioriza e aceita as entregas na review; o TL cuida dos padrões técnicos; os devs implementam. O autor pode mergear o próprio PR sem aprovação de outra pessoa (decisão do time em 2026-11-02).
- **Branches:** hoje o trabalho vai para `dev`, e a `main` recebe PR de `dev`. As branches curtas de item (`tipo/ID-descricao`) saem de `dev`.
- **Origem:** a DoR e a DoD abaixo completam as do [`docs/product-backlog.md`](../product-backlog.md), seções 9 e 10.
- **Segurança:** toda correção de segurança tem relatório em `docs/security/correcao-*.md` (causa, mudança, testes, impacto e riscos residuais), escrito com testes que falham antes da correção.
- **Documentação viva:** toda mudança que afeta segurança atualiza o `threat-model.md` e a arquitetura (antigo DOC-001, agora TK-001).

## Git
- `main` sempre implantável e protegida; trabalho em branches curtas: `tipo/ID-descricao`
  (ex.: `feat/US-012-login`, `fix/BUG-004-timeout`, `sec/SEC-003-rate-limit`).
- Commits pequenos no padrão **Conventional Commits**, citando o ID: `feat(auth): login com MFA (US-012)`.
- Todo merge na `main` passa por **Pull Request** com o template preenchido (DoD).
- Todo merge passa por PR, mas **não exige aprovação de outra pessoa**: antes de mergear, o próprio autor lê o diff inteiro e confere o CI verde. Revisão de outra pessoa ou `/code-review` é recomendada para mudanças de segurança, sem ser obrigatória.
- Releases com tag SemVer (`v0.1.0`) ao fim de cada marco; CHANGELOG atualizado.
- **Nunca** versionar segredos: `.env` no `.gitignore`, `.env.example` só com valores fictícios.

## Definition of Ready (DoR) — item pode entrar na sprint quando
- [ ] Objetivo e contexto entendidos (story Como/quero/para quando for história de usuário)
- [ ] Critérios de aceite verificáveis (Dado/Quando/Então)
- [ ] Estimado e cabe em uma sprint (≤ 8 pts; se não, quebrar)
- [ ] Dependências conhecidas e não bloqueantes
- [ ] **Impacto de segurança avaliado** (none/low/medium/high); se medium/high, há critério de cenário negado/abuso

## Definition of Done (DoD) — item só está pronto quando
- [ ] Critérios de aceite atendidos e demonstráveis
- [ ] Código integrado na `dev` via PR, com CI verde e o diff relido pelo autor (a `main` recebe a `dev` na release)
- [ ] Testes relevantes escritos e passando no CI (incluindo o cenário negado, se houver)
- [ ] Nenhum segredo, credencial ou dado pessoal real adicionado ao repositório
- [ ] Logs não expõem dados sensíveis; erros não vazam detalhes internos
- [ ] Documentação atualizada (README, ADR, API, riscos, `docs/security/threat-model.md` — o que se aplicar)
- [ ] Mudança que afeta o front registrada no arquivo de mudanças para o front (fora do git)
- [ ] Impactos/riscos de segurança avaliados (risco novo → docs/risks/risk-register.md)
- [ ] Evidência registrada no item (PR, teste, commit, print)
- [ ] Teste existente alterado ou removido: relatório no registro do item e aprovação do usuário antes do commit
- [ ] `python3 scripts/dod_check.py <ID>` verde (registro em `docs/roadmap/execucao/<ID>.md`)

## Ética de testes de segurança
- Testes ofensivos só no próprio ambiente ou com autorização explícita por escrito.
- Dados fictícios sempre que bastarem; nunca dados pessoais reais em dev/teste.
- Vulnerabilidade achada em sistema de terceiros: comunicar ao responsável, não explorar.
- IA pode apoiar, mas quem entrega revisa, entende e responde por tudo.
