# Arquitetura do Sistema e Fronteiras de Confiança (v1)

## 1. Contexto e Domínio do Sistema

O **OneCheck** é uma plataforma de gestão de vistorias e locações imobiliárias projetada para imobiliárias, administradores, vistoriadores e locatários. A API RESTful centraliza o controle de acesso, cadastro de propriedades com geolocalização automática, emissão e assinatura de laudos periciais de vistoria de entrada e saída, além de auditoria rigorosa de todas as operações.

### Perfis de Acesso (RBAC)
- **Administrador (`admin`):** Acesso irrestrito a configurações, usuários, auditoria e operações do sistema. Exige MFA obrigatório.
- **Gestor (`gestor`):** Gestão operacional de imóveis, vistorias e contratos. Exige MFA obrigatório.
- **Vistoriador (`vistoriador`):** Realização e preenchimento técnico de checklists de vistoria e registro de avarias. Exige MFA obrigatório.
- **Locatário (`locatario`):** Visualização de contratos e imóveis vinculados, aceite ou contestação de laudos periciais de vistoria.

---

## 2. Diagrama de Arquitetura e Fronteiras de Confiança

```mermaid
flowchart TD
    subgraph ZonaExterna["Zona Externa (Não Confiável)"]
        ClienteWeb["Cliente Web / Mobile (Frontend)"]
        Atacante["Atacante / Terceiros"]
    end

    subgraph Fronteira1["Fronteira de Confiança 1 (Rede Pública / TLS)"]
        direction TB
        subgraph APIGateway["Backend FastAPI (OneCheck Core)"]
            CORSMiddleware["CORS & Request Sanitizer"]
            AuthDep["JWT & Role Dependency (RBAC)"]
            
            subgraph Routers["Roteadores de Negócio"]
                AuthRouter["Auth & MFA Router (/auth)"]
                UserRouter["Usuários Router (/usuarios)"]
                ImovelRouter["Imóveis Router (/imoveis)"]
                ContratoRouter["Contratos Router (/contratos)"]
                ChecklistRouter["Checklists Router (/checklists)"]
                LogRouter["Auditoria Router (/logs)"]
            end
            
            AuditService["Serviço de Auditoria (Append-Only Log)"]
            GeocodingService["Geocoding Service (Nominatim / ViaCEP)"]
        end
    end

    subgraph Fronteira2["Fronteira de Confiança 2 (Camada de Dados Interna)"]
        Database[("Banco de Dados Relacional\n(SQLite / PostgreSQL)\n- Usuários & Hashes\n- Imóveis & Endereços\n- Contratos & Checklists\n- Logs de Auditoria")]
        LocalStorage[("Storage Local / S3\n- Fotos de Vistoria")]
    end

    subgraph Fronteira3["Fronteira de Confiança 3 (Serviços Externos de Terceiros)"]
        ViaCEP["API ViaCEP (Consulta CEP)"]
        Nominatim["OpenStreetMap Nominatim (Geocoding)"]
    end

    %% Fluxos
    ClienteWeb -->|HTTPS / JSON Bearer JWT| CORSMiddleware
    Atacante -.->|Tentativa de Bypass / IDOR| CORSMiddleware
    CORSMiddleware --> AuthDep
    AuthDep --> Routers
    Routers --> AuditService
    Routers --> Database
    Routers --> LocalStorage
    ImovelRouter --> GeocodingService
    GeocodingService -->|HTTP GET / Timeout 5s| ViaCEP
    GeocodingService -->|HTTP GET / Timeout 5s| Nominatim
    AuditService -->|Insert Log com IP e Payload| Database
```

---

## 3. Fronteiras de Confiança (Trust Boundaries)

| Fronteira | Descrição | Nível de Risco | Controles Implementados |
|---|---|---|---|
| **FC-01: Internet ➔ Backend** | Ponto de entrada de requisições públicas de navegadores, apps e atacantes. | **Alto** | - TLS/HTTPS compulsório.<br>- Validação estrita de schema e tipos com Pydantic.<br>- Autenticação JWT (HS256) com tempo de vida curto (15 min) e Refresh Token rotativo.<br>- Fluxo de MFA (TOTP) obrigatório para roles administrativas com setup bloqueante no login. |
| **FC-02: Backend ➔ Banco de Dados / Storage** | Acesso às tabelas relacionais, credenciais protegidas e arquivos de mídia. | **Crítico** | - ORM SQLAlchemy com consultas parametrizadas (proteção total contra SQL Injection).<br>- Senhas hasheadas via Bcrypt com salt aleatório.<br>- Segredos MFA criptografados/armazenados com isolamento.<br>- Soft delete com flag `ativo` em cascata impedindo perda acidental de dados.<br>- Tabela de auditoria `log_operacoes` em modo append-only. |
| **FC-03: Backend ➔ APIs Externas (ViaCEP / Nominatim)** | Saída de requisições do backend para serviços de terceiros para enriquecimento de endereço. | **Médio** | - Requisições com timeout curto e explícito (5 segundos).<br>- Tratamento de exceções com fallback gracioso (Fail-safe: não quebra a requisição caso a API externa esteja fora).<br>- User-Agent customizado e sanitização rigorosa de parâmetros de busca. |

---

## 4. Controles Arquiteturais Chave

1. **Autenticação e Gestão de Sessões:**
   - Senhas protegidas com `bcrypt` (fator de custo padrão da biblioteca).
   - JWT emitido com `sub`, `role`, `type` e `exp`.
   - Refresh tokens opacos armazenados em banco como hash SHA-256 e revogados após rotação ou logout.
2. **Autorização Granular (RBAC + ABAC/Contextual):**
   - Dependência `require_roles("admin", ...)` para autorização por papel.
   - Validação contextual de propriedade (locatário só acessa imóveis, contratos e checklists vinculados a contratos ativos onde ele é o titular).
3. **Validação de Entrada e Imutabilidade de Estado:**
   - Schemas Pydantic tipados com restrições de tamanho, regex e enums válidos.
   - Máquina de estados para checklists e contratos (ex.: laudo finalizado ou imóvel locado com restrição de exclusão).
4. **Trilha de Auditoria e Não-Repúdio:**
   - Cada mutação de estado registra autor, entidade, ID da entidade, IP do cliente e payload JSON no banco de dados.
