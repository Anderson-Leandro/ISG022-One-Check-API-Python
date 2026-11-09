# ADR-0014: CPF cifrado em repouso, com a chave fora do banco

- **Status:** aceito
- **Data:** 2026-11-09
- **Itens relacionados:** SEC-031, R-014, SEC-014 (CPF mascarado e validado)

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
O CPF dos usuários ficava em texto na coluna `usuarios.cpf`. As respostas já o mascaram (SEC-014), mas quem tem acesso direto ao banco ou a um backup lê todos (R-014; LGPD art. 46, CWE-311). O CPF não é usado para busca, ordenação nem unicidade: só é gravado e lido com o usuário.

## Decisão
- **Cifra:** Fernet, da biblioteca `cryptography`, que o projeto já usa: AES-128-CBC com HMAC-SHA256, um IV aleatório por gravação e autenticação do conteúdo. A coluna guarda o token, que é diferente a cada gravação do mesmo CPF.
- **Onde:** um `TypeDecorator` (`app/cpf_cifrado.py`) na coluna, que cifra ao gravar e decifra ao ler. As rotas, os serializadores e as respostas não mudam.
- **Chaves:**
  - `CPF_CHAVES` (variável de ambiente), uma lista separada por vírgula. A primeira cifra e todas decifram (`MultiFernet`).
  - Cada segredo é derivado com SHA-256 para os 32 bytes do Fernet, então serve qualquer segredo longo, inclusive o `generateValue` do Render.
  - É obrigatória fora de desenvolvimento, com 32+ caracteres e diferente da chave pública de desenvolvimento, como o `JWT_SECRET`.
- **Migração na inicialização** (`ensure_schema_updates`): alarga a coluna no PostgreSQL e no MySQL e cifra os CPFs ainda em texto. Ela não decifra nada, então um CPF ilegível não impede a API de subir.
- **Rotação por script** (`scripts/rotacionar_chave_cpf.py`, com conferência e `--aplicar`, usando o `MultiFernet.rotate`), em quatro passos. A nova chave entra primeiro só para leitura (`<antiga>,<nova>`), depois como atual (`<nova>,<antiga>`). Então o script recifra, e a antiga só sai quando a conferência mostra zero CPFs com outra chave e zero ilegíveis. Assim, durante a troca gradual de instâncias do Render, nenhuma instância encontra um CPF que não consegue ler.
- **Fail secure:** um CPF cifrado com uma chave que não está em `CPF_CHAVES` levanta erro. A API não devolve o token nem um valor vazio no lugar do CPF.

## Alternativas consideradas
- **Cifra no banco (pgcrypto):** a chave iria nas consultas e nos logs do banco, e prenderia a API ao PostgreSQL.
- **Cifrar o disco ou o backup inteiro:** depende do provedor (Render), não protege quem tem acesso ao banco em execução e não está sob controle do projeto.
- **Hash do CPF:** não serve, porque o CPF precisa voltar completo para o próprio usuário e para admin e gestor.
- **AES-GCM com uma biblioteca própria:** o Fernet já traz versão, IV e autenticação num formato padrão, com menos código para errar.

## Consequências
- Perder `CPF_CHAVES` torna os CPFs gravados ilegíveis. A chave precisa de cópia segura fora do banco e do backup.
- Quem tem o banco **e** a chave continua lendo os CPFs (risco residual do R-014).
- Buscar ou garantir unicidade por CPF passaria a exigir um índice cego (HMAC do CPF), que não existe hoje porque nenhuma rota precisa.
- O `docker-compose.yml` e o `render.yaml` passam a exigir ou gerar a chave.
- No primeiro deploy, enquanto a instância antiga (sem o SEC-031) ainda atende, ela pode mostrar o token no lugar do CPF de quem já foi cifrado. É uma janela única e curta. Os ambientes atuais serão zerados, então não há dado real nessa situação.
- Um valor sem o prefixo do token é tratado como CPF em texto, de antes da mudança, e é cifrado na próxima inicialização.
