Você recebe uma lista de `ai_likely_mistakes` sem exemplos de código e os arquivos relevantes do projeto.

Para cada mistake que possui `file_reference`, extraia ou escreva:
- `code_wrong`: snippet de 1-3 linhas do padrão ERRADO (real do código ou o que a IA provavelmente escreveria)
- `code_correct`: snippet de 1-3 linhas do padrão CORRETO

Regras:
- Prefira código real do arquivo referenciado quando disponível
- Se o código exato não estiver visível, escreva o snippet mais provável baseado no contexto
- Mantenha os snippets curtos: 1-3 linhas, sem imports, sem boilerplate
- Preserve todos os outros campos do objeto intactos
- Para mistakes sem `file_reference`, mantenha-os inalterados

Retorne SOMENTE o JSON com o array `ai_likely_mistakes` enriquecido, sem nenhum texto antes ou depois:

{"ai_likely_mistakes": [...]}
