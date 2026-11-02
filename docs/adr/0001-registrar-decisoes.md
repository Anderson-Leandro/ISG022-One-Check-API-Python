# ADR-0001: Registrar decisões de arquitetura em ADRs

- **Status:** aceito
- **Data:** 2026-11-02
- **Itens relacionados:** DEBT-009, TK-001

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
As decisões do projeto estão espalhadas: em `docs/architecture/architecture-v1.md`, nos relatórios de correção (`docs/security/correcao-*.md`) e em mensagens de commit. Ao adotar a gestão por roadmap e backlog, é preciso um lugar único e curto para cada decisão, ligado aos itens do backlog e aos riscos.

## Opções consideradas
1. **ADRs em Markdown em `docs/adr/`.** Prós: versionados junto do código, revisados no PR, simples. Contras: dependem de disciplina para serem escritos.
2. **Seção de decisões no documento de arquitetura.** Prós: um arquivo só. Contras: cresce sem histórico, e é difícil marcar uma decisão como substituída.
3. **Wiki ou issues do GitHub.** Prós: fáceis de comentar. Contras: ficam fora do repositório e se perdem num fork.

## Decisão
Vamos usar a opção 1: um arquivo `docs/adr/NNNN-titulo.md` por decisão, no modelo deste, numerado em sequência. Um ADR não é apagado: quando a decisão muda, o antigo passa a "substituído por ADR-XXXX".

Escreve-se um ADR quando a decisão:
- escolhe uma tecnologia ou um padrão;
- aceita um risco;
- muda um contrato da API;
- resolve um spike (SPK-*).

## Consequências
- **Positivas:** contexto preservado; spikes terminam com um artefato; a defesa do projeto tem rastreabilidade.
- **Negativas / custos:** alguns minutos por decisão. As decisões já tomadas precisam de ADRs retroativos (DEBT-009).
- **Segurança:** riscos aceitos passam a ter um ADR, além da entrada em `docs/risks/risk-register.md`.
