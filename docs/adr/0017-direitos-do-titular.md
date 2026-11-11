# ADR-0017: Direitos do titular em autoatendimento: exportar e anonimizar a própria conta

- **Status:** aceito
- **Data:** 2026-11-11
- **Itens relacionados:** SEC-028, R-016, SEC-025 (log append-only), SEC-031 (CPF cifrado)

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
A LGPD (art. 18) garante ao titular o acesso aos dados, a portabilidade e a eliminação. A API não tinha como o usuário obter os próprios dados, e a exclusão era só lógica (`ativo=False`), mantendo nome, e-mail e CPF. Ao mesmo tempo, laudos, aceites e atualizações de problema são evidência de um contrato e precisam continuar válidos, e o log de auditoria é append-only (SEC-025) e guarda registros de acesso pelo prazo do Marco Civil (art. 15).

## Decisão
Decisão do PO em 2026-11-11: **autoatendimento, sempre sobre o próprio usuário.** Não há rota com o id de outra pessoa.
- **Exportação:** `GET /usuarios/me/dados`, em JSON. Traz o perfil com o CPF completo, os contratos como locatário, as vistorias realizadas, os aceites e as atualizações de problema escritas. Do log vêm os próprios eventos (ação, entidade, detalhes, payload, IP e data) e os eventos de outras pessoas sobre a conta (ação, detalhes e data, sem o id nem o IP de quem fez). A exportação também vai para o log.
- **Anonimização:** `POST /usuarios/me/anonimizar`, com reautenticação: senha e, com autenticador, o código. Na hora:
  - o nome vira "Usuário removido", o e-mail vira `removido-<id>@anonimizado.invalid` (único e inválido) e o CPF é apagado;
  - a senha vira um valor aleatório, o MFA é zerado, a conta é desativada e as sessões são revogadas;
  - contratos, vistorias, aceites e atualizações continuam, apontando para o mesmo id. Um laudo gerado depois mostra "Usuário removido";
  - o log registra a anonimização só com o id.
- **Último admin ativo:** não pode se anonimizar (`409`), para o sistema não ficar sem administração. As linhas dos admins ficam travadas até o commit, então dois pedidos ao mesmo tempo não passam juntos.
- **Minimização no log:** o login, a criação e a desativação de usuário deixam de gravar o e-mail no log. O id já identifica a conta, e um texto gravado no log append-only não acompanharia a anonimização.

## Alternativas consideradas
- **Pedido aprovado por um admin:** dá mais controle, mas exige uma tabela de pedidos e mais rotas, e atrasa o atendimento do direito.
- **Manter o nome nos laudos já aceitos** (cópia do nome no laudo, por obrigação contratual, art. 16, I): preserva a leitura do laudo antigo, mas guarda dado pessoal fora do controle da anonimização. Fica para uma decisão futura, se o negócio exigir.
- **Excluir a conta de fato:** quebraria as chaves dos laudos e dos logs, que são evidência.

## Consequências
- **A anonimização não tem volta.** O e-mail fica livre para um novo cadastro, que será outra conta.
- **O log de auditoria continua** com o id, o IP e, nos eventos gravados antes desta mudança, o e-mail em texto (login, criação e desativação de usuário). Ele é append-only e guarda registros de acesso por obrigação legal (Marco Civil, art. 15; LGPD, art. 16, I), até a retenção (`LOG_RETENCAO_DIAS`).
- **O CPF é apagado do registro em uso.** Backups antigos ainda o têm, cifrado (SEC-031), até expirarem.
- **Uma conta desativada por um admin** não consegue mais entrar, então não exerce os dois direitos por estas rotas. O pedido dessa pessoa precisa de outro caminho (DEBT-022).
