import { Logo } from "@/components/brand/Logo";
import { NavItems } from "@/components/layout/NavItems";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle,
  Code2,
  Coins,
  FileSearch,
  Layers,
  RefreshCw,
  Shuffle,
  TrendingDown,
  Users,
  X,
  Zap,
} from "lucide-react";
import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ── */}
      <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-sm border-b border-border/40">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <Logo size={26} />
            <span className="font-bold text-sm tracking-tight">MAES</span>
          </Link>
          <NavItems />
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex-1">
        <div className="max-w-5xl mx-auto px-6 space-y-24 py-16">
          {/* ── Hero ── */}
          <section className="relative space-y-8 py-8">
            {/* Grid background with radial fade */}
            <div
              className="absolute inset-0 bg-grid -z-10"
              style={{
                maskImage:
                  "radial-gradient(ellipse 80% 60% at 50% 0%, black 40%, transparent 100%)",
                WebkitMaskImage:
                  "radial-gradient(ellipse 80% 60% at 50% 0%, black 40%, transparent 100%)",
              }}
            />

            <div className="space-y-5 max-w-3xl">
              <Badge variant="outline" className="text-xs gap-1.5 px-3 py-1">
                <span className="text-cta">✦</span>
                <span>
                  Plataforma de Context &amp; Agent Engineering · v1.2.0
                </span>
              </Badge>

              <h1 className="text-5xl md:text-6xl font-bold tracking-tight leading-[1.1]">
                Dê memória, regras e governança aos{" "}
                <span className="bg-gradient-maes bg-clip-text text-transparent">
                  agents de IA do seu time.
                </span>
              </h1>

              <p className="text-xl text-muted-foreground leading-relaxed max-w-2xl">
                MAES é a plataforma de Context Engineering para AI coding
                agents. Capture compliance, decisões arquiteturais e contratos
                em arquivos que viajam com o repositório — e que Claude Code,
                Cursor, Copilot, Windsurf, Continue e qualquer cliente MCP
                carregam automaticamente.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3">
              <Link href="/docs/foundations/why-maes-exists">
                <Button size="lg" className="gap-2 shadow-glow">
                  O que é o MAES
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/docs/getting-started/installation">
                <Button size="lg" variant="outline">
                  Instalar agora
                </Button>
              </Link>
            </div>

            <p className="text-xs text-muted-foreground">
              <code>maes init</code> + <code>maes sync</code> · IA que conhece
              seu domínio · Sem reinventar contexto a cada sessão
            </p>

            <div className="flex flex-wrap gap-6 text-sm text-muted-foreground">
              <span className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success flex-none" />
                Claude, Cursor, Copilot, Continue, Windsurf
              </span>
              <span className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success flex-none" />
                MCP server nativo — contexto sob demanda
              </span>
              <span className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-success flex-none" />
                Core CLI determinístico — zero API key
              </span>
            </div>
          </section>

          {/* ── O Problema ── */}
          <section className="space-y-10 text-center">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-cta">
                O Problema
              </p>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight max-w-2xl mx-auto leading-tight">
                Usar IA sem contexto humano é código tecnicamente correto mas
                organizacionalmente errado.
              </h2>
              <p className="text-muted-foreground max-w-md mx-auto">
                a IA vê seu código — mas não o que está por trás dele
              </p>
            </div>

            <div className="grid md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-border max-w-3xl mx-auto">
              {[
                {
                  icon: RefreshCw,
                  title: "A IA vê o código, não o contexto",
                  desc: "Não sabe por que o módulo legado existe, qual workaround não pode ser removido, qual regra de compliance não está documentada.",
                },
                {
                  icon: Shuffle,
                  title: "Decisões corretas pelo código, erradas pelo domínio",
                  desc: "A IA sugere remover a integração aparentemente morta — que tem contrato ativo. Sugere IDs sequenciais — que violam PCI.",
                },
                {
                  icon: Users,
                  title: "Contexto humano fica na cabeça",
                  desc: "O que cada dev sabe sobre o projeto não viaja com o repositório. Cada sessão nova, cada dev novo — a IA recomeça sem memória.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="flex flex-col items-center gap-3 px-8 py-6"
                >
                  <div className="h-10 w-10 rounded-lg bg-destructive/10 flex items-center justify-center">
                    <item.icon className="h-5 w-5 text-destructive" />
                  </div>
                  <p className="font-semibold text-sm">{item.title}</p>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Before / After ── */}
          <section className="space-y-8">
            <div className="text-center space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Sem MAES vs. Com MAES
              </p>
              <h2 className="text-3xl font-bold tracking-tight">
                Mesmo prompt. Resultado diferente.
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto">
                A diferença não está na ferramenta de IA — está no contexto que
                você injeta nela.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              {/* Sem MAES */}
              <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 space-y-4">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded-full bg-destructive/15 flex items-center justify-center">
                    <X className="h-3.5 w-3.5 text-destructive" />
                  </div>
                  <span className="font-semibold text-sm text-destructive">
                    Sem MAES
                  </span>
                </div>
                <div className="text-xs font-mono bg-background/60 rounded-lg p-3 text-muted-foreground border border-border/50">
                  "Crie um endpoint para cadastro de usuário"
                </div>
                <ul className="space-y-2">
                  {[
                    "Sugere remover integração aparentemente morta (tem contrato ativo)",
                    "Usa IDs sequenciais — viola compliance de pagamento",
                    "Remove workaround que parece código morto mas existe por razão",
                    "Reinventa arquitetura que já foi descartada pelo time",
                  ].map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-sm text-muted-foreground"
                    >
                      <X className="h-3.5 w-3.5 text-destructive flex-none mt-0.5" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Com MAES */}
              <div className="rounded-xl border border-success/30 bg-success/5 p-6 space-y-4">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded-full bg-success/15 flex items-center justify-center">
                    <CheckCircle className="h-3.5 w-3.5 text-success" />
                  </div>
                  <span className="font-semibold text-sm text-success">
                    Com MAES
                  </span>
                </div>
                <div className="text-xs font-mono bg-background/60 rounded-lg p-3 text-muted-foreground border border-border/50">
                  "Crie um endpoint para cadastro de usuário"
                </div>
                <ul className="space-y-2">
                  {[
                    "Sabe que a integração SOAP tem contrato ativo — não sugere remover",
                    "Usa UUID porque sabe que IDs sequenciais violam seu compliance",
                    "Mantém o workaround porque sabe por que ele existe",
                    "Respeita a decisão arquitetural já descartada pelo time",
                  ].map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-sm text-muted-foreground"
                    >
                      <CheckCircle className="h-3.5 w-3.5 text-success flex-none mt-0.5" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          {/* ── O custo invisível da IA ── */}
          <section className="space-y-10">
            <div className="text-center space-y-3 max-w-3xl mx-auto">
              <p className="text-xs font-semibold uppercase tracking-widest text-cta">
                O Problema Invisível
              </p>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight leading-tight">
                O custo da IA no desenvolvimento não está na geração de código —
                está na{" "}
                <span className="bg-gradient-maes bg-clip-text text-transparent">
                  reconstrução de contexto
                </span>
                {"."}
              </h2>
              <p className="text-muted-foreground leading-relaxed">
                Cada nova sessão, cada novo prompt, cada novo agente — a IA
                precisa reler arquivos, reentender arquitetura, reinferir
                convenções. Você paga por esse trabalho em tokens, todas as
                vezes.
              </p>
            </div>

            {/* Hierarquia de consumo */}
            <div className="rounded-xl border border-border bg-muted/20 p-6 md:p-8 space-y-5">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-lg bg-cta/10 flex items-center justify-center">
                  <Coins className="h-4 w-4 text-cta" />
                </div>
                <div>
                  <p className="font-semibold text-sm">
                    Onde os tokens realmente são gastos
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Hierarquia aproximada, do mais caro ao mais barato
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                {[
                  {
                    rank: 1,
                    label: "Entendimento de sistemas grandes",
                    detail: "monorepos · arquitetura completa · auditorias",
                    width: "w-full",
                    tone: "bg-destructive/70",
                  },
                  {
                    rank: 2,
                    label: "Planejamento complexo",
                    detail: "refactors · migrações · roadmap técnico",
                    width: "w-[88%]",
                    tone: "bg-destructive/60",
                  },
                  {
                    rank: 3,
                    label: "Revisão de PR grande",
                    detail: "múltiplos arquivos · comparação de mudanças",
                    width: "w-[74%]",
                    tone: "bg-warning/70",
                  },
                  {
                    rank: 4,
                    label: "Debugging complexo",
                    detail: "logs · hipóteses · sistemas distribuídos",
                    width: "w-[60%]",
                    tone: "bg-warning/60",
                  },
                  {
                    rank: 5,
                    label: "Documentação extensa",
                    detail: "ADRs · RFCs · relatórios",
                    width: "w-[48%]",
                    tone: "bg-cta/60",
                  },
                  {
                    rank: 6,
                    label: "Features completas",
                    detail: "múltiplos arquivos e camadas",
                    width: "w-[34%]",
                    tone: "bg-primary/60",
                  },
                  {
                    rank: 7,
                    label: "Código isolado",
                    detail: "função única · snippet · ajuste pontual",
                    width: "w-[18%]",
                    tone: "bg-success/60",
                  },
                ].map((row) => (
                  <div
                    key={row.rank}
                    className="grid grid-cols-[2rem_1fr] md:grid-cols-[2rem_minmax(0,1fr)_minmax(0,1fr)] gap-3 items-center"
                  >
                    <span className="text-xs font-mono text-muted-foreground">
                      #{row.rank}
                    </span>
                    <div className="space-y-0.5 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {row.label}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {row.detail}
                      </p>
                    </div>
                    <div className="hidden md:block">
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div className={`h-full ${row.width} ${row.tone}`} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="pt-3 border-t border-border/60">
                <p className="text-sm leading-relaxed">
                  <span className="font-semibold text-foreground">
                    80–95% do custo de tokens
                  </span>{" "}
                  vem de{" "}
                  <span className="text-cta font-medium">
                    leitura e contexto
                  </span>
                  . Apenas{" "}
                  <span className="font-semibold text-foreground">5–20%</span>{" "}
                  vem de escrever código.
                </p>
              </div>
            </div>

            {/* Padrões ruins */}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 space-y-4">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded-full bg-destructive/15 flex items-center justify-center">
                    <X className="h-3.5 w-3.5 text-destructive" />
                  </div>
                  <span className="font-semibold text-sm text-destructive">
                    Padrões que queimam tokens
                  </span>
                </div>
                <ul className="space-y-2.5">
                  {[
                    "Reenviar contexto repetido — re-pagar pelo mesmo entendimento todo prompt",
                    "Arquivos gigantes de instrução (CLAUDE.md / prompts monolíticos)",
                    "Agentes genéricos carregando contexto excessivo",
                    "Enviar o repositório inteiro quando 2–3 arquivos resolvem",
                  ].map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-sm text-muted-foreground"
                    >
                      <X className="h-3.5 w-3.5 text-destructive flex-none mt-0.5" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-xl border border-success/30 bg-success/5 p-6 space-y-4">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded-full bg-success/15 flex items-center justify-center">
                    <TrendingDown className="h-3.5 w-3.5 text-success" />
                  </div>
                  <span className="font-semibold text-sm text-success">
                    O que economiza tokens (Context Engineering)
                  </span>
                </div>
                <ul className="space-y-2.5">
                  {[
                    "Mandar só o necessário: task + arquivos relevantes + constraints + output esperado",
                    "Hierarquia de contexto: Project → Domain → Feature → Task",
                    "Agentes especializados: architect, backend, QA, metrics",
                    "Artefatos intermediários: arch summaries, inferred maps, domain models",
                  ].map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 text-sm text-muted-foreground"
                    >
                      <CheckCircle className="h-3.5 w-3.5 text-success flex-none mt-0.5" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Posicionamento MAES */}
            <div className="rounded-xl border border-primary/30 bg-primary/5 p-6 md:p-8 space-y-5">
              <div className="flex items-start gap-4">
                <div className="h-10 w-10 rounded-lg bg-primary/15 flex items-center justify-center flex-none">
                  <FileSearch className="h-5 w-5 text-primary" />
                </div>
                <div className="space-y-2">
                  <h3 className="font-semibold text-lg leading-tight">
                    MAES resolve isso estruturando contexto — em vez de depender
                    de contexto bruto.
                  </h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Em vez de cada sessão da IA reler o repositório, o MAES
                    compila um contexto determinístico e reutilizável que viaja
                    com o repositório. A IA carrega apenas a fatia relevante —
                    sempre.
                  </p>
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-3 pt-2">
                {[
                  "Reduz carga de leitura da IA em cada sessão",
                  "Evita reprocessamento de repositórios inteiros",
                  "Transforma contexto humano em artefatos reutilizáveis",
                  "Torna workflows previsíveis e determinísticos",
                ].map((item) => (
                  <div
                    key={item}
                    className="flex items-start gap-2 text-sm text-foreground/85"
                  >
                    <CheckCircle className="h-3.5 w-3.5 text-primary flex-none mt-0.5" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* ── As 6 Camadas ── */}
          <section className="space-y-10">
            <div className="text-center space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-cta">
                Arquitetura
              </p>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight max-w-2xl mx-auto leading-tight">
                Seis camadas. Uma fonte de verdade.
              </h2>
              <p className="text-muted-foreground max-w-2xl mx-auto">
                MAES não é uma CLI a mais. É infraestrutura organizada em
                camadas que cobrem todo o ciclo de contexto para AI coding
                agents.
              </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
              {[
                {
                  layer: "Context Layer",
                  desc: "human/ + inferred/. Compliance, decisões, contratos, stack e padrões detectados — versionados no repo.",
                },
                {
                  layer: "Compiler Layer",
                  desc: "Pipeline determinístico de 7 estágios. Normaliza, deduplica, resolve conflitos e prioriza por camada.",
                },
                {
                  layer: "Agent Layer",
                  desc: "Slash commands externos (/maes-analyze, /maes-context-add, /maes-eval) + agents fixos especializados.",
                },
                {
                  layer: "Documentation Layer",
                  desc: "Adapters gerados por cliente: CLAUDE.md, .cursor/rules/, .github/instructions/, .windsurfrules, .continue/rules/.",
                },
                {
                  layer: "MCP Layer",
                  desc: "Server stateless que entrega contexto sob demanda — agents consultam apenas o relevante, sem inflar prompt inicial.",
                },
                {
                  layer: "Governance Layer",
                  desc: "OWNERSHIP.yaml, staleness, CI gates. Cada camada tem dono, prazo de revisão e bloqueio em PR quando crítica.",
                },
              ].map((item) => (
                <div
                  key={item.layer}
                  className="rounded-lg border border-border/60 bg-card/40 p-5 space-y-2"
                >
                  <div className="text-sm font-semibold text-cta">
                    {item.layer}
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Como Funciona ── */}
          <section className="space-y-8">
            <div className="text-center space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Como Funciona
              </p>
              <h2 className="text-3xl font-bold tracking-tight">
                Três etapas. Setup em minutos.
              </h2>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              {[
                {
                  step: "01",
                  title: "maes init",
                  desc: "Scaffold determinístico de .maes/ + instalação dos agentes (/maes-analyze, /maes-context-add) no seu cliente de IA. Depois do init, rode /maes-analyze no cliente para gerar o contexto inferido inicial — fora do core, usando o provider do próprio cliente.",
                  color: "text-primary",
                },
                {
                  step: "02",
                  title: "Capture o que a IA não infere",
                  desc: "Edite compliance.md, decisions.md, business-rules.md. Use o agente /maes-context-add para extrair regras de docs existentes — o compilador roteia para o arquivo correto automaticamente.",
                  color: "text-cta",
                },
                {
                  step: "03",
                  title: "maes sync + CI gate",
                  desc: "maes sync compila tudo em CLAUDE.md, .cursor/rules/ e copilot-instructions.md. maes validate no CI bloqueia merge se o contexto ficar stale em layers críticas.",
                  color: "text-success",
                },
              ].map((item) => (
                <div key={item.step} className="space-y-3">
                  <span
                    className={`text-4xl font-bold ${item.color} opacity-40`}
                  >
                    {item.step}
                  </span>
                  <h3 className="font-semibold text-lg">{item.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Para quem é MAES ── */}
          <section className="space-y-10">
            <div className="text-center space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-cta">
                Para quem é MAES
              </p>
              <h2 className="text-3xl md:text-4xl font-bold tracking-tight max-w-2xl mx-auto leading-tight">
                Times que querem que IA escale o senior — não substitua.
              </h2>
            </div>

            <div className="grid md:grid-cols-3 gap-4 max-w-5xl mx-auto">
              {[
                {
                  who: "Times com mais de 2 devs usando IA",
                  why: "Alinha contexto entre todos — ninguém reinventa decisão na sua sessão.",
                },
                {
                  who: "Repositórios com decisões não óbvias",
                  why: "Compliance, segurança, contratos e escolhas arquiteturais ficam versionadas.",
                },
                {
                  who: "Engineering leaders e tech leads",
                  why: "Governança real: ownership, staleness, CI gates. Contexto vira infraestrutura.",
                },
              ].map((item) => (
                <div
                  key={item.who}
                  className="rounded-lg border border-border/60 bg-card/40 p-5 space-y-2"
                >
                  <div className="text-sm font-semibold">{item.who}</div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {item.why}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Multi-tool ── */}
          <section className="space-y-8">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Compatibilidade
              </p>
              <h2 className="text-3xl font-bold tracking-tight">
                Um contexto. Todas as ferramentas.
              </h2>
              <p className="text-muted-foreground max-w-xl leading-relaxed">
                Escreva o contexto uma vez. Cada ferramenta lê no formato que
                conhece. Troque de editor amanhã sem reescrever nada.
              </p>
            </div>

            <div className="rounded-xl border border-border bg-muted/20 p-6 md:p-8 space-y-6">
              {/* Source */}
              <div className="flex items-center gap-3">
                <div className="px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/20 text-xs font-mono font-semibold text-primary">
                  .maes/context/human/
                </div>
                <span className="text-xs text-muted-foreground">
                  fonte de verdade do time
                </span>
              </div>

              {/* Arrow */}
              <div className="flex items-center gap-2 text-muted-foreground/40">
                <div className="h-px flex-1 bg-border" />
                <ArrowRight className="h-4 w-4" />
                <div className="h-px flex-1 bg-border" />
              </div>

              {/* Tools grid */}
              <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  {
                    tool: "Claude Code",
                    file: "CLAUDE.md",
                    note: "Carregado automaticamente em toda sessão",
                    accent: "border-primary/30 bg-primary/5",
                    badge: "bg-primary/10 text-primary",
                  },
                  {
                    tool: "Cursor",
                    file: ".cursor/rules/",
                    note: "Injetado como regras globais do editor",
                    accent: "border-cta/30 bg-cta/5",
                    badge: "bg-cta/10 text-cta",
                  },
                  {
                    tool: "GitHub Copilot",
                    file: "copilot-instructions.md",
                    note: "Regras de repositório para o Agent Mode",
                    accent: "border-success/30 bg-success/5",
                    badge: "bg-success/10 text-success",
                  },
                  {
                    tool: "Windsurf",
                    file: ".windsurfrules",
                    note: "Carregado pelo Cascade em cada sessão",
                    accent: "border-warning/30 bg-warning/5",
                    badge: "bg-warning/10 text-warning",
                  },
                  {
                    tool: "Continue",
                    file: ".continue/rules/",
                    note: "Carregado automaticamente pelo Continue",
                    accent: "border-primary/30 bg-primary/5",
                    badge: "bg-primary/10 text-primary",
                  },
                ].map((t) => (
                  <div
                    key={t.tool}
                    className={`rounded-lg border p-4 space-y-2 ${t.accent}`}
                  >
                    <span
                      className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-md ${t.badge}`}
                    >
                      {t.tool}
                    </span>
                    <p className="text-xs font-mono text-foreground/80">
                      {t.file}
                    </p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {t.note}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <p className="text-sm text-muted-foreground">
                <CheckCircle className="inline h-3.5 w-3.5 text-success mr-1.5 -mt-0.5" />
                Execute{" "}
                <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                  maes sync
                </span>{" "}
                para recompilar todos os adapters. Adicione{" "}
                <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                  maes-validate.yml
                </span>{" "}
                ao CI para garantir que o contexto nunca fique stale em
                produção.
              </p>
              <p className="text-sm text-muted-foreground">
                <CheckCircle className="inline h-3.5 w-3.5 text-success mr-1.5 -mt-0.5" />
                Integra com agentes via{" "}
                <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                  maes serve
                </span>{" "}
                — expõe o contexto compilado como MCP server para Claude Desktop
                e outros clientes MCP.
              </p>
            </div>
          </section>

          {/* ── Features ── */}
          <section className="space-y-8">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                Recursos
              </p>
              <h2 className="text-3xl font-bold tracking-tight">
                Stack operacional mínima e integrada
              </h2>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              {[
                {
                  icon: Layers,
                  color: "bg-primary/10 text-primary",
                  title: "Contexto Humano Persistente",
                  desc: "Regras de negócio, rationale arquitetural e restrições organizacionais em arquivos que viajam com o repositório — carregados por Claude Code, Cursor e Copilot automaticamente.",
                  bullets: [
                    "Decisões e restrições que a IA não infere do código",
                    "7 camadas de prioridade — compliance sempre sobrescreve engineering",
                    "Contexto auto-sugerido para atualização pós-merge",
                  ],
                },
                {
                  icon: Zap,
                  color: "bg-cta/10 text-cta",
                  title: "Um contexto, todas as ferramentas",
                  desc: "Escreva o contexto uma vez em .maes/context/human/. O compilador gera automaticamente o formato correto para cada IDE — troque de ferramenta sem reescrever nada.",
                  bullets: [
                    "CLAUDE.md para Claude Code — carregado em toda sessão",
                    ".cursor/rules/ para Cursor — injetado como regras globais",
                    "copilot-instructions.md e .windsurfrules também gerados",
                  ],
                },
                {
                  icon: BarChart3,
                  color: "bg-success/10 text-success",
                  title: "CI bloqueia contexto desatualizado",
                  desc: "Regras de compliance e segurança têm TTL. Quando envelhecem, o CI gate bloqueia o merge automaticamente — a IA nunca trabalha com contexto stale em produção.",
                  bullets: [
                    "Layers 1–3 (compliance, segurança, contratos) — bloqueiam CI",
                    "Layers 4–6 — alertam sem bloquear",
                    "maes validate roda sem API key — só lógica local",
                  ],
                },
                {
                  icon: Code2,
                  color: "bg-warning/10 text-warning",
                  title: "Token Budget Inteligente",
                  desc: "O compilador distribui o contexto em tiers priorizados. Compliance nunca fica de fora — engineering entra apenas quando relevante.",
                  bullets: [
                    "Hot ≤800 tokens — layers 1-3, sempre carregado em todo prompt",
                    "Warm ≤4000 tokens — layers 4-6, carregado por relevância à tarefa",
                    "CI falha se hot context exceder 800 tokens",
                  ],
                },
              ].map((f) => (
                <div
                  key={f.title}
                  className="p-6 rounded-xl border border-border hover:border-primary/50 transition-colors space-y-4"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`h-10 w-10 rounded-lg flex items-center justify-center ${f.color}`}
                    >
                      <f.icon className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-lg">{f.title}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {f.desc}
                  </p>
                  <ul className="space-y-1.5">
                    {f.bullets.map((b) => (
                      <li
                        key={b}
                        className="flex items-center gap-2 text-sm text-muted-foreground"
                      >
                        <CheckCircle className="h-3.5 w-3.5 text-success flex-none" />
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>

          {/* ── Governança ── */}
          <section className="space-y-8">
            <div className="grid md:grid-cols-2 gap-10 items-center">
              <div className="space-y-4">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Governança
                </p>
                <h2 className="text-3xl font-bold tracking-tight leading-tight">
                  Contexto que não envelhece.
                </h2>
                <p className="text-muted-foreground leading-relaxed">
                  Arquivos de contexto ficam desatualizados silenciosamente — e
                  a IA começa a dar output errado sem ninguém perceber.
                </p>
                <p className="text-muted-foreground leading-relaxed">
                  O MAES roda um relatório de governança toda semana. Ele
                  classifica cada arquivo por idade, detecta placeholders não
                  preenchidos e alerta antes que o drift cause problema.
                </p>
                <ul className="space-y-2">
                  {[
                    "Staleness automático por idade de commit",
                    "Fill rate: detecta templates não preenchidos",
                    "Alerta quando decisões ficam em excesso",
                    "Archive automático de decisões antigas",
                  ].map((item) => (
                    <li
                      key={item}
                      className="flex items-center gap-2 text-sm text-muted-foreground"
                    >
                      <CheckCircle className="h-3.5 w-3.5 text-success flex-none" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Mini dashboard */}
              <div className="rounded-xl border border-border bg-muted/20 p-5 space-y-3 font-mono text-xs">
                <div className="flex items-center gap-2 text-muted-foreground mb-4">
                  <Activity className="h-3.5 w-3.5" />
                  <span className="font-sans text-xs font-semibold">
                    MAES Governance Report
                  </span>
                </div>

                {[
                  {
                    file: "compliance.md",
                    age: "2d",
                    status: "fresh",
                    icon: "✅",
                  },
                  {
                    file: "business-rules.md",
                    age: "9d",
                    status: "fresh",
                    icon: "✅",
                  },
                  {
                    file: "integrations.md",
                    age: "21d",
                    status: "aging",
                    icon: "🟡",
                  },
                  {
                    file: "decisions.md",
                    age: "43d",
                    status: "stale",
                    icon: "🟠",
                  },
                  {
                    file: "principles.md",
                    age: "68d",
                    status: "critical",
                    icon: "🔴",
                  },
                ].map((row) => (
                  <div
                    key={row.file}
                    className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0"
                  >
                    <span className="text-foreground/70">{row.file}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-muted-foreground">{row.age}</span>
                      <span>
                        {row.icon} {row.status}
                      </span>
                    </div>
                  </div>
                ))}

                <div className="pt-2 text-muted-foreground font-sans text-xs">
                  <span className="text-destructive font-semibold">
                    1 arquivo critical
                  </span>{" "}
                  — atualizar hoje antes de continuar trabalho
                </div>
              </div>
            </div>
          </section>

          {/* ── Layers ── */}
          <section className="space-y-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                Arquitetura
              </p>
              <h2 className="text-3xl font-bold tracking-tight">
                7 camadas de prioridade
              </h2>
              <p className="text-muted-foreground mt-1">
                Compliance sempre ganha. Engineering nunca sobrescreve
                compliance. Inferred nunca sobrescreve nada.
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                {
                  num: 1,
                  name: "Compliance",
                  color: "bg-destructive/10 text-destructive",
                  desc: "Legal, PII, audit — hot context",
                },
                {
                  num: 2,
                  name: "Security",
                  color: "bg-warning/10 text-warning",
                  desc: "Auth, tokens, injeção — hot context",
                },
                {
                  num: 3,
                  name: "Contracts",
                  color: "bg-cta/10 text-cta",
                  desc: "APIs externas, SLAs — hot context",
                },
                {
                  num: 4,
                  name: "Architecture",
                  color: "bg-primary/10 text-primary",
                  desc: "ADRs, decisões de stack",
                },
                {
                  num: 5,
                  name: "Domain",
                  color: "bg-success/10 text-success",
                  desc: "Regras de negócio, invariantes",
                },
                {
                  num: 6,
                  name: "Engineering",
                  color: "bg-secondary text-secondary-foreground",
                  desc: "Padrões do time, convenções",
                },
                {
                  num: 7,
                  name: "Inferred",
                  color: "bg-muted/50 text-muted-foreground",
                  desc: "Auto-detectado — somente leitura",
                },
              ].map((layer) => (
                <div
                  key={layer.num}
                  className="p-4 rounded-xl border border-border hover:bg-muted/50 transition-colors"
                >
                  <div
                    className={`inline-flex items-center justify-center w-7 h-7 rounded-md text-xs font-bold mb-2.5 ${layer.color}`}
                  >
                    {layer.num}
                  </div>
                  <p className="font-semibold text-sm">{layer.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {layer.desc}
                  </p>
                </div>
              ))}
            </div>

            <div className="pt-2">
              <Link href="/docs/architecture/context-layer">
                <Button variant="outline" className="gap-2">
                  Ver arquitetura completa
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </section>

          {/* ── CTA ── */}
          <section className="rounded-xl bg-gradient-maes p-8 md:p-12 text-white space-y-5">
            <div className="space-y-2">
              <h2 className="text-3xl font-bold tracking-tight">
                Pronto para começar?
              </h2>
              <p className="text-white/75 text-lg max-w-xl leading-relaxed">
                Instale MAES em qualquer projeto Git. Sem lock-in, sem SaaS —
                tudo versionado no seu repositório.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <Link href="/docs/foundations/why-maes-exists">
                <Button
                  size="lg"
                  className="bg-white text-primary hover:bg-white/90 gap-2"
                >
                  O que é o MAES
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/docs/getting-started/installation">
                <Button
                  size="lg"
                  variant="outline"
                  className="bg-transparent border-white/30 text-white hover:bg-white/10 hover:text-white"
                >
                  Instalar agora
                </Button>
              </Link>
            </div>
          </section>
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-border/40 py-6">
        <div className="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Logo size={16} />
            <span>© 2026 Maxxi · MAES Framework</span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/docs/foundations/why-maes-exists"
              className="hover:text-foreground transition-colors"
            >
              Docs
            </Link>
            <a
              href="https://github.com/Maxxidata/maxxi-ai-engineering-system"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
