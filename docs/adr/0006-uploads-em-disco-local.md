# ADR-0006: Fotos gravadas em disco local (`UPLOAD_DIR`)

- **Status:** aceito (registro retroativo; decisão tomada em 2026-06, com a validação revista em 2026-10-25)
- **Data:** 2026-11-08
- **Itens relacionados:** DEBT-009, SEC-002, SPK-002, TK-018, T-12, T-14, R-017

> **Por que isso importa:** daqui a 6 meses ninguém lembra por que escolheu X. O ADR guarda o
> contexto e as alternativas, e evita rediscutir a mesma decisão.

## Contexto
O vistoriador anexa uma foto a cada item do checklist, e o locatário anexa fotos aos problemas. As fotos são evidência do laudo (ativo A-08) e mostram o interior das casas. A versão em PHP gravava os arquivos numa pasta do servidor, e a migração manteve o modelo para não depender de serviço pago.

## Opções consideradas
1. **Disco local do processo, numa pasta configurável.**
   - Prós: nenhuma dependência nem custo; simples de testar (cada teste usa uma pasta temporária).
   - Contras: o arquivo vive onde o processo roda; não escala para mais de uma instância; depende de o disco ser persistente.
2. **Armazenamento de objetos (S3, R2, Supabase Storage) com URL assinada.**
   - Prós: durável, independente da instância, URL com validade.
   - Contras: conta e credenciais a mais; custo; mudança no upload e no download.
3. **Imagem dentro do banco (coluna binária).**
   - Prós: o backup do banco leva as fotos.
   - Contras: banco maior e mais lento; o plano gratuito do Postgres tem pouco espaço.

## Decisão
Vamos usar a **opção 1**:
- **Pasta:** `UPLOAD_DIR` (`app/config.py:50`, padrão `uploads/`). No Docker Compose local, um volume nomeado (`uploads:/app/uploads`).
- **Gravação** (`app/uploads.py`):
  - o tipo vem do conteúdo, nunca do nome ou do `Content-Type`: assinatura conferida antes do Pillow, parser restrito a JPEG, PNG e WebP, limite de 25 megapixels (SEC-002, T-12);
  - nome aleatório de 128 bits (`uuid4().hex`) com a extensão do tipo detectado;
  - tamanho máximo de `MAX_UPLOAD_MB` (10 MB).
- **Entrega:** `GET /api/v1/uploads/{arquivo}` (`app/routers/health.py:15`), sem login; `caminho_seguro` impede sair da pasta e as respostas levam `nosniff` e `CSP sandbox`.
- **Troca e exclusão:** enviar uma foto nova para o item apaga a anterior do disco e do banco.

## Consequências
- **Positivas:**
  - nenhum serviço externo nem credencial a mais;
  - a validação do conteúdo fica num módulo só e testado.
- **Negativas / custos:**
  - **durabilidade depende do disco do deploy.** O `render.yaml` não declara disco persistente, e, pela documentação do Render, o sistema de arquivos do plano gratuito é efêmero: o que foi gravado se perde a cada deploy ou reinício. Registrado em 2026-11-08 como risco R-017 e item TK-018, a confirmar no painel do Render;
  - as fotos não entram no backup do banco (TK-005 cobre só o banco);
  - com mais de uma instância, cada uma só vê as fotos que ela mesma gravou.
- **Segurança:**
  - as fotos são servidas sem login; a proteção é o nome impossível de adivinhar. Quem recebe ou vaza uma URL vê a foto para sempre (T-14). A decisão sobre isso é o SPK-002.
