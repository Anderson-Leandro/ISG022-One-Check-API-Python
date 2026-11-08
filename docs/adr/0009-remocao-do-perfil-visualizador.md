# ADR-0009: Remoção do perfil visualizador

- **Status:** aceito
- **Data:** 2026-11-08
- **Itens relacionados:** SPK-001, DEBT-015, ADR-0005, ADR-0011

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
O perfil `visualizador` lê a operação inteira: imóveis com endereço e coordenadas, contratos, agendamentos, vistorias e os PDFs dos laudos, que trazem nome e e-mail do locatário. Não vê problemas nem usuários. O alcance dele estava "a confirmar" desde o modelo de ameaças, e o SPK-001 pedia a decisão entre leitura global e leitura recortada.

Nenhuma conta com esse perfil foi criada: o seed não o usa, e os ambientes de desenvolvimento e de produção serão zerados.

## Opções consideradas
1. **Leitura global (como estava).** Prós: nenhum código. Contras: uma conta vazada lê a operação inteira, e ninguém usa o perfil.
2. **Leitura recortada por carteira.** Prós: menor privilégio. Contras: um vínculo novo para manter, para um perfil sem uso.
3. **Leitura global sem dados pessoais.** Prós: minimização. Contras: o mesmo perfil sem uso, com mais código.
4. **Remover o perfil.** Prós: menos superfície de ataque e menos regras de acesso para manter. Contras: quem precisar de leitura interna usa outro perfil.

## Decisão
Vamos usar a **opção 4**, decidida pelo usuário (PO) em 2026-11-08. A remoção é feita no DEBT-015:
- `visualizador` sai de `ROLES` (`app/auth.py`) e das regras de leitura; criar ou alterar um usuário com esse perfil responde 422;
- **sem migração de contas**: nenhuma existe, e os ambientes serão recriados;
- **o modelo `Usuario` deixa de ter perfil padrão** (hoje é `visualizador`): todo usuário nasce com um perfil explícito;
- **fail secure**: `get_current_user` recusa token ou conta com perfil fora de `ROLES`. As regras de `app/deps.py` restringem só locatário e vistoriador e liberam os outros perfis; sem essa checagem, um perfil desconhecido gravado no banco (um script, um erro de digitação, um perfil removido no futuro) ganharia acesso total.

## Consequências
- **Positivas:**
  - cinco perfis viram quatro: as matrizes de acesso e os testes ficam menores;
  - um perfil inesperado nunca ganha acesso, em vez de ganhar acesso total.
- **Negativas / custos:**
  - os testes que exercitam o visualizador saem ou mudam (com relatório e aprovação, no DEBT-015);
  - documentos históricos de auditoria continuam citando o perfil; ficam como registro do que existia.
- **Segurança:** menor privilégio por redução de superfície, e fail secure para perfis fora da lista (OWASP API5:2023, CWE-636).
