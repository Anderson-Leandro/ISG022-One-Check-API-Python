# ADR-0015: IP do cliente pelo item do proxy no X-Forwarded-For

- **Status:** aceito
- **Data:** 2026-11-10
- **Itens relacionados:** SEC-017, R-008, SEC-010 (IP na auditoria), N6 (limite de tentativas)

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
A API roda no Render atrás de um proxy, e o IP do cliente é usado no limite de tentativas (20 falhas por IP em 15 minutos) e na trilha de auditoria (`log_operacao.ip`). O uvicorn rodava com `FORWARDED_ALLOW_IPS="*"`: confiava em todos os itens do `X-Forwarded-For` e ficava com o primeiro.

Em 2026-11-10, um login falho enviado à produção com `X-Forwarded-For: 203.0.113.9` gravou `203.0.113.9` no log. O proxy do Render **acrescenta** o IP real ao cabeçalho do cliente em vez de sobrescrever, então o primeiro item é escolhido pelo cliente. Trocando o valor a cada tentativa, o limite por IP nunca disparava e a auditoria gravava o IP forjado (CWE-348, OWASP API4:2023).

## Decisão
- **Quem decide o IP:** um middleware próprio (`app/ip_cliente.py`), o mais externo da aplicação. Ele troca o `client` do scope antes do limite de tentativas e da auditoria.
- **Qual item:** com `PROXY_SALTOS=N`, o N-ésimo a partir da direita, que é o que o último proxy confiável acrescentou. O que o cliente escreveu à esquerda nunca é usado. No Render, `PROXY_SALTOS=3` (`render.yaml`), conforme a cadeia abaixo.
- **Fail secure:** sem `PROXY_SALTOS` (0, o padrão), o cabeçalho é ignorado. Cabeçalho ausente, com menos itens que os saltos ou com um item que não é IP também caem no IP da conexão, nunca num valor do cliente.
- **Uvicorn:** `start.sh` e `start.ps1` sobem com `--no-proxy-headers`. Assim, um `FORWARDED_ALLOW_IPS="*"` que ainda esteja no painel do Render não volta a ligar a leitura do primeiro item.
- **Esquema:** a flag desliga também o `X-Forwarded-Proto` do uvicorn. O middleware passa a aplicar o último item, o do proxy, aceitando só `http` e `https`. Assim, as URLs que a aplicação monta, como o redirect da barra final, continuam em `https`.

## Cadeia de proxies no Render (conferida em 2026-11-10)
Login falho com `X-Forwarded-For: 203.0.113.9`, repetido com cada valor de `PROXY_SALTOS`:

| `PROXY_SALTOS` | IP gravado | De quem é |
|---|---|---|
| (antes, uvicorn com `*`) | `203.0.113.9` | o valor forjado pelo cliente |
| 1 | `10.26.170.74` | rede interna do Render (faixa privada `10.0.0.0/8`) |
| 2 | `104.22.160.70` | Cloudflare (faixa `104.16.0.0/13`, cloudflare.com/ips) |
| 3 | o IP público de quem testou | o cliente |

O cabeçalho que chega na API é `<forjado>, <cliente>, <Cloudflare>, <rede interna>`. Os IPs da Cloudflare e da rede interna mudam de uma requisição para outra, mas o número de saltos não.

## Alternativas consideradas
- **Restringir `FORWARDED_ALLOW_IPS` à rede do proxy:** a faixa de IPs do proxy do Render não foi conferida e pode mudar sem aviso, e a regra do uvicorn depende de saber quais IPs da cadeia são confiáveis. Com uma faixa errada, ou o cliente volta a escolher o IP, ou todos passam a ter o IP do proxy.
- **Último item fixo, sem configuração:** funciona no Render de hoje, mas quebra o desenvolvimento local, onde não há proxy e o cabeçalho viria só do cliente.
- **Cabeçalho próprio do provedor (como `True-Client-IP`):** prende a API a um provedor e não foi conferido no Render. Se o proxy não o sobrescrever, o cliente também consegue enviá-lo.

## Consequências
- Se o Render passar a usar mais de um proxy que acrescenta itens, o IP gravado vira o de um proxy, e o limite por IP passa a valer para muitos clientes juntos. A conferência depois de cada mudança de infraestrutura é a mesma do SEC-017: um login falho com um `X-Forwarded-For` forjado precisa gravar o IP público real de quem testou. Se gravar outro, ajuste `PROXY_SALTOS`.
- Um proxy a mais ou a menos na frente da API (outro CDN, ou a Cloudflare saindo da frente do Render) muda a contagem. Um valor alto demais devolve o IP forjado, e um baixo demais devolve o IP de um proxy.
- O limite por conta continua sendo a principal barreira contra a força bruta. O limite por IP passa a valer também contra quem troca o cabeçalho.
