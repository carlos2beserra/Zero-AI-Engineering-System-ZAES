export type ModuleType =
  | "REST API"
  | "GraphQL"
  | "gRPC"
  | "Worker"
  | "Frontend"
  | "Library"
  | "CLI"
  | "BFF";

export interface StackConfig {
  frontend: string[];
  backend: string[];
  database: string[];
  cache: string[];
  queue: string[];
  infrastructure: string[];
  cicd: string[];
  monitoring: string[];
}

export interface AnalysisEntity {
  name: string;
  table_or_collection: string;
  notable_columns: string[];
  constraints: string[];
}

export interface AnalysisModule {
  name: string;
  path: string;
  type: ModuleType;
  responsibility: string;
  tech: string;
}

export interface AnalysisJSON {
  _maes_schema_version: "1.0";
  _analyzed_at?: string;
  _analyzer_notes?: string;
  project: {
    name: string;
    description: string;
    primary_domain: string;
  };
  stack: StackConfig;
  modules: AnalysisModule[];
  data_model: {
    conventions: string[];
    entities: AnalysisEntity[];
    notes: string;
    special_indexes: string[];
    special_fields: string[];
  };
  code_patterns: {
    naming_conventions: string[];
    error_handling: string;
    dependency_injection: boolean | string;
    test_patterns: string[];
    notable_patterns: string[];
  };
  infrastructure: {
    deployment: string;
    env_vars_detected: string[];
    ci_cd_workflows: string[];
  };
  gaps: {
    architecture_rationale: string;
    business_rules: string;
    business_rules_inferred: string[];
    behavior_contracts: string[];
    constraints: string;
    warning_antipatterns: string[];
    ai_likely_mistakes: string[];
  };
}

export type ContextFile =
  | "architecture"
  | "business-rules"
  | "data-model"
  | "engineering-rules"
  | "claude-md"
  | "cursorrules"
  | "windsurfrules"
  | "ai-operating-rules"
  | "current-state";
