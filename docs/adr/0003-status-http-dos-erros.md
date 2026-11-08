# ADR-0003: Erros de negócio respondem com o status HTTP adequado

- **Status:** aceito
- **Data:** 2026-11-07
- **Itens relacionados:** DEBT-014, DEBT-012, DEBT-013, SEC-021

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
O helper `fail()` (`app/schemas.py:37`) monta o envelope `{"sucesso": false, "erro": "..."}` sem definir status. Por isso o FastAPI responde **200** em todos os erros de regra de negócio:
- 46 handlers seguem esse padrão;
- um deles é uma negação de acesso: `GET /contratos/{id}/checklists`.

O padrão veio da versão original, convertida da API em PHP, e só foi documentado depois (README, "Erros de negócio respondem 200"). Nunca foi uma decisão registrada. A própria API já usa 401, 403, 404, 409, 413, 422 e 429 em outros pontos, então o cliente precisa tratar os dois estilos.

Problemas do 200 com erro dentro:
- **Detecção e auditoria:**
  - login falho, código MFA errado e acesso negado aparecem como 200 nos logs do servidor, do Render e de um eventual WAF;
  - um pico de abuso fica invisível para quem monitora pelos status (OWASP A09:2021, CWE-393 *Return of Wrong Status Code*).
- **Semântica HTTP (RFC 9110):** ferramentas, caches, proxies e clientes genéricos tratam a chamada como bem-sucedida.
- **Contrato:** o OpenAPI só documenta o 200; quem integra não sabe quais erros esperar.

## Opções consideradas
1. **Manter o 200 com `sucesso: false`.**
   - Prós: nenhuma mudança.
   - Contras: todos os problemas acima continuam.
2. **Status adequado e o mesmo envelope.**
   - Prós:
     - o corpo não muda: quem já lê o envelope (`sucesso` e `erro`) continua funcionando.
   - Contras: revisar 46 handlers e os testes que conferem 200 em falha.
3. **Status adequado e corpo `application/problem+json` (RFC 9457).**
   - Prós: é o padrão mais recente.
   - Contras: troca o formato do corpo; exige mudança em todos os clientes e na documentação, sem ganho de segurança sobre a opção 2.

## Decisão
Vamos usar a **opção 2**. O envelope `{sucesso, dados, erro, erros}` continua, e o status HTTP passa a acompanhar o resultado.

- **`fail()` nunca responde 2xx.** O status passa a ser um parâmetro. Na falta dele, o padrão é **400**, nunca 200 (fail secure).
- **Tabela de status:**

  | Situação | Status |
  |---|---|
  | Regra de negócio violada que não se encaixa abaixo (datas incoerentes, operação não permitida no estado atual sem conflito de versão) | 400 |
  | Sem autenticação válida: token ausente, inválido ou expirado; **login, MFA ou refresh recusados** | 401 |
  | Autenticado, mas sem permissão para a ação ou o recurso; reautenticação recusada com sessão válida (senha ou código atual errados em rota autenticada) | 403 |
  | Recurso não encontrado, ou não visível para quem pede | 404 |
  | Conflito com o estado atual: e-mail já cadastrado, imóvel já locado, checklist já enviado, MFA já configurado | 409 |
  | Campo inválido, com `erros: {campo: mensagem}` | 422 |
  | Limite de tentativas | 429 (já existe) |

- **Mensagens:** as mensagens de autenticação continuam genéricas, sem dizer se o e-mail existe nem o que falhou no token.
- **401 só para quem está sem sessão válida.** É comum o cliente HTTP tratar o 401 como "sessão expirada": renova o token e repete a requisição. Por isso uma senha atual errada em rota autenticada (desligar o MFA, trocar a senha) responde **403**: a sessão é válida, e repetir a tentativa contaria em dobro no limitador.

## Consequências
- **Positivas:**
  - os eventos de segurança (401, 403, 429) ficam visíveis nos logs e no monitoramento;
  - o OpenAPI pode documentar as respostas de erro de cada rota;
  - a API fica com um estilo só.
- **Negativas / custos:**
  - testes de falha que conferem `status_code == 200` mudam junto (DEBT-014);
  - a collection do Insomnia é gerada de novo;
  - o `README.md` é atualizado.
- **Segurança:** melhora a detecção de abuso (A09) sem mudar quem pode fazer o quê. Os testes de negação passam a conferir o status exato (DEBT-012).
