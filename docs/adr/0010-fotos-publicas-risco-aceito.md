# ADR-0010: Fotos servidas sem login: risco aceito até o armazenamento externo

- **Status:** aceito
- **Data:** 2026-11-08
- **Itens relacionados:** SPK-002, SEC-026, TK-018, R-007, R-017, ADR-0006

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
`GET /api/v1/uploads/{arquivo}` entrega as fotos de vistoria e de problemas sem login (ADR-0006). A proteção é o nome aleatório de 128 bits: ninguém adivinha uma URL, mas quem recebe ou vaza uma URL vê a foto do interior do imóvel sem prazo (ameaça T-14, risco R-007, nível baixo). Ao mesmo tempo, o disco do plano gratuito do Render provavelmente é efêmero (R-017, TK-018), o que deve levar as fotos para um armazenamento externo.

## Opções consideradas
1. **Aceitar o risco por enquanto.** Prós: nenhum código agora. Contras: uma URL vazada continua valendo.
2. **URL assinada com validade sobre o disco local (SEC-026).** Prós: URL vazada expira; continua funcionando em `<img src>`. Contras: seria refeita quando as fotos mudarem de armazenamento.
3. **Download autenticado.** Prós: o mais forte. Contras: o cliente deixa de poder usar a URL direto numa imagem.

## Decisão
Vamos usar a **opção 1**, decidida pelo usuário (PO) em 2026-11-08. O R-007 passa a risco aceito, e a revisão fica amarrada à adoção de um **serviço externo de armazenamento** das fotos (armazenamento de objetos, como S3 ou R2). Esse serviço já entrega URL assinada com validade, então o SEC-026 deve ser feito junto com essa troca, e não antes.

## Consequências
- **Positivas:** nenhum retrabalho: a proteção da URL vem com o armazenamento novo.
- **Negativas / custos:** até lá, uma URL de foto vazada continua abrindo a foto.
- **Segurança:** risco residual baixo (P1 × I2), aceito e registrado no registro de riscos, com revisão na adoção do armazenamento externo.
