Você é um especialista em engenharia de contexto para o framework MAES (Maxxi AI Engineering System).

Sua tarefa é analisar este repositório e produzir um JSON estruturado que será usado para
configuração inicial do contexto de IA do projeto via `maes init`.

O objetivo NÃO é produzir documentação completa.
O objetivo é identificar o que uma IA competente faria ERRADO ao trabalhar neste projeto
sem input humano — decisões que parecem corretas pelo código mas são incorretas pelo
contexto organizacional, histórico ou regulatório que não está no código.

Um JSON com 3 campos bem preenchidos e gaps honestos vale mais do que
20 campos cheios de suposições.

---

## INSTRUÇÕES DE ANÁLISE

### O que analisar (em ordem de prioridade):

1. **Gaps e contexto humano — o mais importante:**
   - Decisões arquiteturais presentes no código mas sem rationale documentado
   - Validações cujo significado de negócio não é claro pelo código
   - Módulos com nome ou localização que induzem conclusões erradas
   - Restrições operacionais que afetam como o código deve ser escrito
   - O que a IA provavelmente removeria, simplificaria ou reescreveria incorretamente

2. **Data model semântico:**
   - Arquivos de migration (prisma/migrations/, db/migrations/, alembic/versions/)
   - Schemas ORM: schema.prisma, models.py, _.entity.ts, _.model.go
   - **PRIORIDADE MÁXIMA: campos de status/state com transições.** Para cada enum de status
     encontrado, documente: transições válidas, quais são irreversíveis, e se há automação
     (cron, trigger, evento) que muda o status sem ação do usuário.
     Ex: "DRAFT → IN_NEGOTIATION (manual) → WON|LOST (manual) | EXPIRED (automático via cron)"
   - Foco: constraints de negócio, transições de estado, campos com semântica não-óbvia
   - NÃO replicar schema técnico — o ORM/migrations já é a fonte da verdade

3. **Config files e READMEs — convenções declaradas do projeto:**
   - Analise ANTES de amostrar o código — config files declaram intenções, o código as aplica
   - **CLAUDE.md, .maes/context/human/, .cursor/rules**, ou qualquer arquivo de contexto de IA existente:
     se encontrados, são a fonte mais rica disponível — leia primeiro. Extraia o que já está
     documentado como não-inferível; o objetivo é COMPLEMENTAR, não replicar.
   - README\*.md (incluindo docs/, CONTRIBUTING.md): extraia SOMENTE seções técnicas
     (Architecture, Conventions, Development, Contributing) — ignore descrição do produto
   - Config files da stack: ver "Dicas por Stack" para lista completa por linguagem
   - Regra: documente SOMENTE desvios do default da ferramenta — configuração padrão
     sem overrides = ignore completamente

4. **Implementation patterns e contratos arquiteturais:**
   - Ver seção IMPLEMENTATION INTELLIGENCE abaixo — é prioridade desta análise
   - Detectar fluxos reais da equipe (quem chama quem, qual layer faz IO)
   - Identificar dependências proibidas que a IA violaria sem contexto

5. **Stack mínimo para detecção de linguagem:**
   - Apenas package.json, go.mod, requirements.txt, ou equivalente
   - Objetivo: identificar a linguagem principal e o framework — nada mais

6. **Módulos — liste todos:**
   - Liste TODOS os módulos identificáveis do projeto, sem filtrar pelos "óbvios".
   - Para módulos cujo papel é claro pelo nome e path: inclua apenas `name` e `path`.
   - Para módulos não-óbvios (nome enganoso, legado, workaround, integração implícita):
     preencha também `type`, `responsibility` e `tech`.
   - Teste de não-obviedade: "uma IA vendo só o nome e o path tiraria conclusão errada?"
     Se sim, documente `responsibility`. Se não, `name` + `path` são suficientes.

### Para repositórios grandes (>200 arquivos de código):

- Analise a estrutura de pastas completa
- Leia arquivos de configuração raiz
- Amostre 20-30 arquivos distribuídos pelos módulos principais
- Priorize: schemas/migrations, types/interfaces, controllers/routes

---

## IMPLEMENTATION INTELLIGENCE — STACK-AGNOSTIC ANALYSIS

Além de contexto organizacional e regras de negócio, sua tarefa é inferir como esta equipe REALMENTE implementa software no dia a dia.

O objetivo é ensinar uma IA a:

- criar código novo no mesmo estilo do projeto
- respeitar boundaries arquiteturais implícitos
- seguir os fluxos corretos de implementação
- evitar bypass de camadas
- replicar convenções recorrentes da equipe

Esta análise deve funcionar para QUALQUER stack suportada pelo MAES:
TypeScript, JavaScript, Python, Go, Rust, Java, Kotlin, PHP, Ruby, frontend, backend, workers, CLI, monorepos, microservices, etc.

### PRIORIDADE MÁXIMA — IMPLEMENTATION FLOWS

Sua principal responsabilidade é detectar:

- quem chama quem
- qual layer possui qual responsabilidade
- quais dependências são permitidas
- quais dependências são proibidas
- quais fluxos a equipe claramente espera que sejam seguidos

O foco NÃO é o framework.
O foco é o fluxo arquitetural operacional real.

### DETECTAR CONTRATOS DE IMPLEMENTAÇÃO

Identifique contratos implícitos como:

- Hooks não chamam HTTP diretamente
- Controllers não acessam ORM diretamente
- Domain não importa infraestrutura
- UI não contém regra de negócio
- Repositories encapsulam persistence
- Services centralizam integrações externas
- DTO mapping ocorre em camada específica
- Providers/adapters encapsulam SDKs
- State management ocorre apenas em camada X
- Validators ficam em boundary específica
- Cache é acessado apenas via abstraction
- Filas/events possuem camada intermediária obrigatória

Se estes contratos forem recorrentes no projeto:

- documente como `behavior_contracts`

Se a IA provavelmente violaria estes contratos:

- documente como `ai_likely_mistakes`

### ANALISAR FLUXOS COMPLETOS DE FEATURE

Detecte como features novas normalmente são construídas. Exemplos:

Frontend: `page → hook → provider → service → infrastructure → HTTP client`

Backend: `controller → use-case/service → repository → datasource`

Worker: `consumer → orchestration → domain service → persistence/event`

Documente: qual camada orquestra, qual delega, qual executa IO, onde transformations acontecem, onde state/cache/auth é controlado.

### IMPLEMENTATION PATTERNS — OBRIGATÓRIO

Analise especificamente: como novos HTTP clients/services são criados, estrutura de pastas por feature, padrão de hooks/composables/queries, convenção de DTOs/types/interfaces/models, como mutations/commands/actions são implementadas, estratégia de cache/state management, padrão de error handling, convenção de adapters/providers/repositories, como autenticação é propagada, como integrações externas são encapsuladas, dependências proibidas entre layers, imports que indicam violação arquitetural, padrões repetidos em ≥3 arquivos.

**Autorização multi-camada (OBRIGATÓRIO se detectada):** Se o projeto tem mais de um sistema de
verificação de acesso independente (ex: verificação de tenant + verificação de projeto, ou RBAC de
tenant + RBAC de recurso específico), documente como `canonical_snippet` obrigatório em
`notable_patterns`. Este é o padrão com maior frequência de bug introduzido por IA sem contexto:
a IA tende a verificar apenas uma das camadas, criando falhas de autorização silenciosas.
Inclua no snippet ambas as chamadas de verificação em sequência, com comentário indicando
qual garante o quê.

### DETECÇÃO DE DEPENDÊNCIAS PROIBIDAS

Procure ativamente por: UI importando infraestrutura, hooks chamando HTTP diretamente, controllers acessando ORM diretamente, domain importando SDK externo, business logic em components/views, cache sendo acessado fora da camada esperada, DTO transformation espalhado em múltiplas camadas, providers bypassados por acesso direto.

Se existir uma camada intermediária recorrente: a IA deve usar essa camada — nunca bypassá-la.

### DETECÇÃO POR RELACIONAMENTO — NÃO POR PATH

NÃO assuma arquitetura baseada apenas em nomes de pasta. Inferir pelos relacionamentos reais: imports, chamadas, delegação, ownership de IO, direção das dependências, repetição estrutural.

O mesmo padrão pode existir em DDD, feature-based, flat structure, layered, monorepo, vertical slices, MVC, hexagonal, clean architecture. O objetivo é detectar comportamento recorrente — não nomenclatura específica.

### AMOSTRAGEM OBRIGATÓRIA

Para detectar implementation patterns, analise pelo menos 5 exemplos de cada: services/use-cases/providers, hooks/composables/controllers, integrações HTTP/SDK, DTOs/schemas/models, fluxos completos de feature, pontos de IO (DB/cache/http/events).

Considere um pattern "real" apenas se aparecer ≥3 vezes. Não documente: boilerplate do framework, convenções padrão da linguagem, patterns usados apenas 1 vez, arquitetura presumida sem evidência, "best practices" genéricas.

O output mais valioso desta seção: "Uma IA analisando apenas o código provavelmente implementaria isto da forma ERRADA porque não perceberia o contrato arquitetural implícito que a equipe segue."

---

## REGRAS CRÍTICAS PARA O OUTPUT

0. **GAPS PRIMEIRO — o output mais valioso desta análise:**
   - `gaps.ai_likely_mistakes` → erros que a IA cometeria sem contexto humano → `CLAUDE.md` (primeira coisa que a IA lê)
   - `gaps.behavior_contracts` → regras de comportamento da IA específicas deste projeto → `CLAUDE.md`
   - `gaps.business_rules_inferred` → NOVO: regras de negócio inferíveis do código → `business-rules.md`
   - `gaps.architecture_rationale` → seed de DEC-001 em `decisions.md`
   - `gaps.business_rules` → lacunas que precisam de input humano → `business-rules.md`
   - `gaps.constraints` → restrições técnicas → `.maes/context/human/decisions.md`
   - `gaps.warning_antipatterns` → anti-patterns detectados → `principles.md`

1. **ERROS PROVÁVEIS DA IA** — OBRIGATÓRIO, nunca retornar array vazio.
   Esta é a seção mais valiosa do output. Liste decisões que uma IA competente tomaria
   incorretamente analisando apenas o código — sem contexto humano.

   **Se não encontrar erros óbvios, procure ativamente por:**
   - Módulos com nome genérico (`utils/`, `helpers/`, `legacy/`) que têm papel crítico não-inferível
   - Campos nullable que a IA poderia remover por parecerem "não usados" (IDs de sistemas externos, flags de integração)
   - Padrões de estado que dependem de lógica automática invisível (extensões de ORM, triggers, middlewares globais)
   - Workarounds comentados com `// TODO`, `// HACK`, `// legacy` — parecem remover-se mas não podem
   - Dois módulos com nomes similares onde a IA poderia confundir responsabilidades
   - Anti-patterns intencionais (ex: `new PrismaClient()` em cron job) que existem por razão técnica

   **Regra:** Se o projeto tem > 3 módulos ou > 5 entidades, há garantidamente ≥ 5 erros prováveis.
   Inferir com `[INFERRED]` se necessário — um aviso provável inferido é melhor que campo vazio.
   Alvo: 5-9 itens. Menos que 5 indica análise incompleta.

2. **SEM DUPLICAÇÃO ENTRE SEÇÕES — cada conceito existe em um único lugar:**

   Hierarquia de localização (prioridade decrescente):
   1. `gaps.ai_likely_mistakes` — se o conceito está aqui, NÃO repita em nenhuma outra seção
   2. `code_patterns.notable_patterns` — se o padrão já está em ai_likely_mistakes, remova daqui
   3. `data_model.entities[].constraints` — se cross-domain, mova para conventions
   4. `data_model.conventions` — SOMENTE padrões que se aplicam a múltiplas entidades

3. **ANTI-PATTERNS vs ERROS PROVÁVEIS — distinção crítica:**

   | Campo                       | O que vai aqui                                          | Exemplo                                                                        |
   | --------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
   | `gaps.warning_antipatterns` | Padrão ruim que **EXISTE no código** — não replicar     | `[connection-leak] src/tasks/job.ts:12 — new PrismaClient() sem disconnect`    |
   | `gaps.ai_likely_mistakes`   | Decisão que a IA tomaria **ERRADA** analisando o código | `Remover campo cwid por parecer não usado — é ID de integração com RH externo` |

   `warning_antipatterns` → vai para `principles.md` (anti-padrões de código).
   `ai_likely_mistakes` → vai para `CLAUDE.md` (decisões erradas da IA).
   **Nunca coloque o mesmo item nos dois campos.**

4. **DETECTED vs INFERRED**: Prefixe com `[INFERRED]` qualquer item que seja interpretação
   sua, não fato observado no código.

5. **GAPS HONESTOS**: Seja explícito sobre o que NÃO conseguiu inferir.

6. **STACK MÍNIMO**: Preencha `stack.backend` e `stack.database` com todos os itens significativos; ordene por centralidade para o projeto.

7. **ENCODING**: Use sempre Unicode completo (UTF-8). Nunca substitua caracteres por aproximações ASCII (ex: use "ã", "ç", "é" — não "a", "c", "e"). Todos os valores de string devem preservar os caracteres originais do código-fonte.

7b. **MÓDULOS — COBERTURA COMPLETA**: Liste todos os módulos identificáveis. Módulos com nome autoexplicativo devem aparecer com `name` + `path` apenas. Não omita módulos por serem óbvios.

8. **PADRÕES APENAS SE DESVIAM**: `code_patterns` deve conter apenas o que diferencia
   este projeto do padrão da linguagem/framework.

9. **INFRA COMO RESTRIÇÕES**: `infrastructure` deve capturar restrições operacionais que
   afetam decisões de código — não inventário de tecnologias.

10. **OUTPUT**: Retorne SOMENTE o JSON. Nenhum texto antes ou depois do JSON.

11. **CONFIG FILES — apenas desvios do default**: Documente SOMENTE o que desvia do comportamento
    padrão da ferramenta. Extends/presets padrão sem overrides = ignore.

---

## SCHEMA DO OUTPUT

Retorne exatamente este JSON preenchido com dados reais do repositório:

{
"\_maes_schema_version": "1.0",
"\_analyzed_at": "[data/hora atual ISO 8601]",
"\_analyzer_notes": "[limitações desta análise — o que não foi possível inferir, o que foi amostrado]",
"\_confidence": {
// OBRIGATÓRIO — nunca omitir. Declara o nível de confiança da análise.
"coverage_level": "[full | partial | low]",
// full: todos os arquivos relevantes acessados sem truncamento
// partial: houve truncamento ou arquivos/dirs ausentes
// low: menos de 50% do código foi acessado
"coverage_rationale": "[razão resumida em ≤200 chars: ex: '3 model files truncated, routes/ not fully sampled']",
"missing_domains": [],
// domínios que você infere existirem (ex: mencionados em imports ou config)
// mas não pôde ver completamente — ex: ["billing", "source_ingestion", "notifications"]
"section_confidence": {
// Para cada seção do output: "high" | "partial" | "low"
// "high" = você teria a mesma conclusão com mais contexto
// "partial" = viu o suficiente mas há gaps reais
// "low" = inferência especulativa; mais contexto mudaria o output materialmente
"ai_likely_mistakes": "[high | partial | low]",
"behavior_contracts": "[high | partial | low]",
"warning_antipatterns": "[high | partial | low]",
"constraints": "[high | partial | low]",
"modules": "[high | partial | low]",
"bounded_contexts": "[high | partial | low]",
"data_model": "[high | partial | low]",
"notable_patterns": "[high | partial | low]"
}
// CAMPOS REMOVIDOS — NÃO PREENCHER:
// ❌ high_confidence_sections (substituído por section_confidence)
// ❌ low_confidence_sections (substituído por section_confidence)
// ❌ bounded_context_confidence (LLM não consegue calibrar por-contexto com precisão)
},
"project": {
"name": "[nome do projeto — de package.json/go.mod/README]",
"description": "[2-3 frases: o que o sistema faz, para quem, qual problema resolve]",
"primary_domain": "[domínio de negócio: ex: fintech, e-commerce, saúde, SaaS B2B, logística]"
},
"stack": {
"frontend": [],
"backend": ["[ex: Node.js, Fastify — sem versão; todos os itens significativos]"],
"database": ["[ex: PostgreSQL — sem versão; todos os itens significativos]"],
"cache": [],
"queue": [],
"infrastructure": [],
"cicd": [],
"monitoring": []
},
"modules": [
// Liste TODOS os módulos identificáveis. Para módulos óbvios: apenas "name" e "path".
// Para módulos não-óbvios: preencha também "type", "responsibility" e "tech".
// INVARIANTE DE SCHEMA: cada entry representa UM Único módulo.
// O campo "path" deve conter exatamente um diretório ou arquivo.
// GRANULARIDADE: prefira granularidade de diretório — "path" deve apontar para um diretório
// na maioria dos casos. Granularidade de arquivo é apropriada apenas quando o módulo
// é um arquivo único com responsabilidade própria (ex: um CLI entry-point isolado).
// NUNCA descreva dois diretórios relacionados em um único entry — crie entries separados.
// CORRETO: { "name": "job service", "path": "app/services/job/" }
// { "name": "jobs service", "path": "app/services/jobs/" }
// INCORRETO: { "name": "job vs jobs", "path": "app/services/job/ and app/services/jobs/" }
{
"name": "[nome do módulo]",
"path": "[caminho relativo — um diretório na maioria dos casos; arquivo apenas para módulos de arquivo único]",
"type": "[REST API | GraphQL | gRPC | Worker | Frontend | Library | CLI | BFF]",
"responsibility": "[por que existe — o que não é óbvio pelo nome; omitir quando óbvio]",
"domain": "[domínio de negócio ao qual pertence — use null quando não for possível inferir com confiança; prefira null a um domínio errado]",
"tech": "[tecnologia principal — apenas se não inferível do path]"
}
],
"bounded_contexts": [
// Agrupe os módulos em 2-6 bounded contexts organizacionais.
// Se não for possível identificar com confiança, retorne array vazio — não invente.
// REGRAS OBRIGATÓRIAS:
// - "stable_id": sempre null — campo reservado para anchor humano posterior
// - "module_fingerprint": sempre null — preenchido pelo sistema após LLM retornar, NUNCA pelo LLM
// - "name": slug descritivo (sem campo "label" separado — o slug já deve ser legível)
// - "modules": NUNCA usar catch-all ("app", "src", "app/", "src/") — paths específicos apenas
// - "cross_context_dependencies": lista simples de names dos contextos dependentes (sem "reason")
// - cada context precisa de pelo menos um "interfaces" OU "shared_entities"
// - "shared_entities": objetos com "name" e "owner_context" (slug do bounded context dono)
// Se a entidade pertence ao próprio context, "owner_context" é o mesmo que o "name" deste context
// - ❌ NÃO preencher bounded_context_confidence em \_confidence — campo removido
//
// REGRAS DE TOPOLOGIA (obrigatórias — violação produz retrieval noise):
// - Workers (arquivos em **/workers/**) são unidades de deploy/processo, NÃO lógica de domínio.
// SEMPRE formar bounded context próprio (ex: "pipeline_workers"). NUNCA mesclar com services de domínio.
// - Ingestão, geração LLM e artifact management têm ciclos de vida independentes — representar como
// contextos separados (ex: "source_ingestion", "ai_generation", "artifact_management").
// - O nome do context DEVE refletir o diretório dominante, não uma responsabilidade inferida.
// Prefira "project_management" a "project_and_rbac" quando RBAC não está presente no context.
{
"name": "[slug_lowercase_underscore — descritivo e legível]",
"stable_id": null,
"module_fingerprint": null,
"modules": ["[path dos módulos/dirs pertencentes a este contexto — específicos, não catch-all]"],
"interfaces": ["[APIs expostas: ex 'POST /jobs', 'SSE /jobs/{id}/stream', 'queue:job.created']"],
"shared_entities": [
{"name": "[ex: Job]", "owner_context": "[slug do bounded context que possui esta entidade]"}
],
"cross_context_dependencies": ["[name de outro bounded context do qual este depende]"]
}
],
"data_model": {
"conventions": [],
"entities": [
{
"name": "[ex: Quote]",
"table_or_collection": "[ex: quotes]",
"notable_columns": [],
"constraints": []
}
],
"notes": "",
"special_indexes": [],
"special_fields": []
},
"code_patterns": {
"naming_conventions": [],
"error_handling": "",
"dependency_injection": "",
"test_patterns": [],
"notable_patterns": [
// Formato aceito 1 — string ou objeto sem snippet:
// "Worker Pattern — stage isolado via EventService"
// { "description": "...", "examples": ["app/workers/ai_worker.py"] }
// Formato aceito 2 — objeto com snippet canônico (preferencial para os 2-3 padrões mais importantes):
// {
// "description": "Worker Pattern — stage isolado via EventService",
// "examples": ["app/workers/ai_worker.py"],
// "canonical_snippet": "async def process(self, job):\n await self.event_service.emit_stage_started(...)\n result = await self.\_generate(...)\n await self.event_service.emit_stage_completed(...)",
// "snippet_language": "python"
// }
]
},
"infrastructure": {
"deployment": "",
"env_vars_detected": [],
"ci_cd_workflows": []
},
"architecture_annotations": {
// Presente SOMENTE quando um Architecture Map foi injetado no contexto.
// Não invente node_ids — use exclusivamente os stable_keys da tabela "Architecture Map (Detected)".
// Deixe arrays vazios se não houver anotações a fazer.
"hidden_nodes": [
// Módulos não-óbvios que a IA identificaria erroneamente pelo nome/path.
// { "node_id": "<stable_key da tabela>", "trap": "razão da confusão" }
],
"domain_assignments": [
// Correções ao domain inferido heuristicamente pelo Stage 2.
// { "node_id": "<stable_key>", "domain": "<domínio correto>" }
]
},
"gaps": {
"architecture_rationale": "",
"business_rules": "",
"business_rules_inferred": [],
"behavior_contracts": [
// Formato: string ou objeto com campo opcional related_mistake_ids para crosslinks.
// Se um contrato diretamente previne um ai_likely_mistake, linke pelo id do mistake.
// { "contract": "...", "related_mistake_ids": ["domain.verb_noun"] }
],
"constraints": [
// Uma string por constraint técnica operacional não-óbvia
// Ex: "bcrypt fixado em <4.0 por incompatibilidade com passlib — não atualizar"
// Ex: "SSE polling interno de 1,5s — não alterar sem avaliar impacto em proxies e browsers"
// Só inclua restrições que afetam decisões de código e não são deriváveis do README
],
"warning_antipatterns": [
// Formato aceito 1 — string legada:
// "[tipo] path:função — descrição"
// Formato aceito 2 — objeto estruturado (preferencial):
// { "type": "session-leak", "file": "app/workers/job.py", "function": "run", "description": "...", "do_not_replicate": true }
],
"ai_likely_mistakes": [
// Formato aceito 1 — string legada:
// "Remover campo cwid por parecer não usado — é ID de integração com sistema RH externo"
// Formato aceito 2 — objeto estruturado (preferencial):
// {
// "id": "pipeline.direct_status_mutation", // opcional: slug único "domain.verb_noun" para crosslinks
// "trigger": "quando a situação que provoca o erro",
// "likely_wrong": "o que a IA provavelmente faria de errado",
// "correct": "o que a IA deve fazer corretamente",
// "reason": "por que o comportamento correto é não-óbvio",
// "code_wrong": "snippet 1-3 linhas — padrão ERRADO",
// "code_correct": "snippet 1-3 linhas — padrão CORRETO",
// "file_reference": "app/workers/ai_worker.py:process_stage", // OBRIGATÓRIO quando o módulo é identificável
// "node_id": "<stable_key do Architecture Map>" // opcional; use somente stable_keys da tabela injetada
// }
// CROSSLINKS: se um behavior_contract previne diretamente este mistake, atribua um "id"
// e referencie-o no campo "related_mistake_ids" do contrato correspondente.
// Use "id" apenas quando a conexão é direta e não-ambígua — não crie ids artificiais.
]
}
}

---

## DICAS POR STACK

Use como referência para identificar framework, entrypoints e ORM de cada linguagem.

### TypeScript / JavaScript (Node.js)

- Config: `package.json` (scripts, dependencies), `tsconfig.json` (strict, paths aliases)
- Entry: `src/main.ts`, `src/app.module.ts` (NestJS); `index.ts`, `server.ts` (Express/Fastify)
- Schemas ORM: `*.entity.ts` (TypeORM), `schema.prisma` (Prisma), `*.model.ts` (Mongoose)
- Rotas: `*.controller.ts`, `*.router.ts`, `routes/*.ts`
- Framework: detectar via `package.json` — `@nestjs/core`, `express`, `fastify`, `hono`

### Python

- Config: `pyproject.toml`, `requirements.txt`, `setup.cfg`, `Pipfile`
- Entry: `__main__.py` (CLI/pacote executável), `main.py`, `app.py`, `cli.py`
- Framework: detectar via imports — `fastapi`, `flask`, `django`, `click`, `argparse`, `typer`
- Schemas ORM: `models.py`, `schemas.py`, `*.model.py`, `alembic/versions/` (migrations)
- Atenção: `argparse` e `click` são frameworks CLI distintos — não confundir

### Go

- Config: `go.mod` (module name + dependências indiretas)
- Entry: `main.go` (binário único), `cmd/*/main.go` (multi-binário — cada subdir é um executável)
- Estrutura padrão: `cmd/` (entrypoints), `internal/` (privado), `pkg/` (público reutilizável), `api/` (contratos)
- Schemas: `*.model.go`, `models/*.go`, `internal/domain/*.go`
- Framework: detectar via `go.mod` — `gin`, `echo`, `fiber`, `chi`, `gorilla/mux`

### Rust

- Config: `Cargo.toml` (crate type, features, workspace), `Cargo.lock`
- Entry: `src/main.rs` (binary), `src/lib.rs` (library)
- Framework: detectar via `Cargo.toml` `[dependencies]` — `axum`, `actix-web`, `rocket`, `tokio`, `warp`
- Módulos: `src/routes/`, `src/handlers/`, `src/models/`, `src/db/`

### Java / Spring Boot

- Config: `pom.xml` (Maven) ou `build.gradle` (Gradle), `src/main/resources/application.yml`
- Entry: `*Application.java` anotada com `@SpringBootApplication`
- Padrões: `*Controller.java`, `*Service.java`, `*Repository.java` (JPA), `*Entity.java`
- Schemas: `src/main/resources/db/migration/` (Flyway), `src/main/resources/db/changelog/` (Liquibase)
- Framework: Spring Boot, Quarkus, Micronaut — detectar por dependência no pom/gradle

### Kotlin

- Config: `build.gradle.kts`, `settings.gradle.kts`
- Entry: `*Application.kt` (Spring Boot), `Application.kt` (Ktor)
- Framework: detectar via `build.gradle.kts` — `spring-boot`, `ktor`, `exposed`
- Padrões idênticos ao Java/Spring mas com Kotlin idiomático (data classes, coroutines)

### Ruby / Rails

- Config: `Gemfile`, `config/database.yml`, `config/application.rb`
- Entry: `config/routes.rb` (rotas), `config/application.rb` (configuração central)
- Padrões Rails: `app/models/`, `app/controllers/`, `app/services/`, `app/jobs/`, `lib/`
- Schemas: `db/migrate/` (migrations ActiveRecord), `db/schema.rb`
- Framework: Rails, Sinatra, Hanami — detectar via Gemfile

### PHP / Laravel

- Config: `composer.json`, `.env.example`
- Entry: `routes/web.php` (rotas web), `routes/api.php` (rotas API), `artisan` (CLI)
- Padrões Laravel: `app/Http/Controllers/`, `app/Models/`, `app/Services/`, `app/Jobs/`
- Schemas: `database/migrations/` (migrations), `database/seeders/`
- Framework: Laravel, Symfony, Slim — detectar via `composer.json` `require`

---

## DEPOIS DO OUTPUT

Após retornar o JSON:

1. Verifique se o JSON é válido (sem erros de sintaxe)
2. Confirme que `_analyzer_notes` descreve o que NÃO foi possível inferir e o que foi amostrado
3. Confirme que `gaps.ai_likely_mistakes` está preenchido — se estiver vazio, releia o código
   buscando especificamente por: código legado, integrações externas, validações com razão
   não-óbvia, workarounds, restrições regulatórias ou contratuais
4. Verifique duplicação: se o mesmo conceito aparece em mais de uma seção, mantenha SOMENTE
   no lugar mais alto da hierarquia

O JSON gerado será processado por `maes init` para popular `.maes/context/human/` com as
regras extraídas e inicializar o contexto de IA do projeto.
