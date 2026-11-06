# Instruções do repositório

- Leia `docs/ESTADO-ATUAL.md` e `PLANO.md`; documentos históricos podem conter etapas superadas.
- Alvo exclusivo MIKRO MK1. Não presumir número de tile, encapsulamento/pino ou modelo de periférico apenas pela ordem dos segmentos.
- Testes padrão são offline; nunca acessar USB, serviço NI, DFU, FL aberto ou flash na CI.
- Não implementar gravação de firmware como efeito colateral de scripts de análise, build ou testes.
- Preserve capturas e presets locais. O build público não pode sobrescrever um bundle local de presets existente.
- Não versionar materiais excluídos por `.gitignore`; confira `publication-manifest.json` antes de publicar.
- Dados próprios de captura podem gerar fixtures mínimas, com proveniência, sem identidade da unidade ou caminhos pessoais.
- Não alterar configurações musicais a partir de picos de força manual sem validação explícita.
- Validação rápida: `python test_16_pads.py`, `python test_display.py`, `node test_encoder.cjs`.
- Verificações diferenciais são opcionais e exigem a FW55 local e seus arquivos derivados; não declarar sucesso quando esses arquivos estiverem ausentes.
- Não atribuir uma licença geral ou licenças de terceiros a conteúdo sem decisão do proprietário e revisão de origem.
