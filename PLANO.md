# Plano de desenvolvimento — MK1 MOD

Data-base: 05/11/2026. Objetivo: transformar o conhecimento experimental em drivers e processamento musical próprios, mantendo o editor e o fluxo FL Studio utilizáveis. A MK1 está fechada; nesta fase trabalhamos com documentação, evidências existentes e testes USB normais combinados com o operador.

## Princípios e ordem de trabalho

Separar o editor de parâmetros, o processamento musical no computador e a futura firmware embarcada. Um mapa de portas não é um esquema elétrico; uma tradução Python não é uma firmware compilada; checksum válido não prova que o dispositivo iniciará. Não substituir uma lacuna por uma suposição silenciosa.

## Etapas e critérios de saída

| Etapa | Trabalho concreto | Critério para concluir | Dependências/estado |
|---|---|---|---|
| 0 — Base pública | README, plano, prompt, seleção de fontes, testes e CI | Clone limpo abre editor básico e passa testes sem arquivos privados | Esta publicação |
| 1 — Especificação rastreável | Consolidar relatórios HID, portas locais, argumentos e evidências | Cada campo/sinal tem origem e nível de confiança; sem atribuir tile/pino não provado | Parcial; vários serviços reconstruídos |
| 2 — Núcleo independente de hardware | Biblioteca portável de encoder, LEDs, display e empacotamento de amostras | Testes determinísticos, comparações com modelos e capturas mínimas; sem APIs USB no núcleo | Encoder/PWM em Python; portar para C depois |
| 3 — Processamento dos pads | Máquina de ataque, pico, release, pressão, curvas e limiares por pad | Uma batida gera um disparo, release correto, curvas monotônicas, ausência de notas presas e disparos duplicados | Padronizar datasets leves/fortes dos 16 pads |
| 4 — Saída musical no host | Integrar núcleo ao editor e a um transporte MIDI explícito | Só os 16 pads geram notas; botões fazem funções; teste real de FL e reconexão | Fluxo NI/FL existente; nova ponte MIDI ainda não implementada |
| 5 — Toolchain XMOS | Identificar ferramenta compatível com XS1 L2, licença e formato de saída | Exemplo mínimo compilado e reproduzível; versão e alvo documentados; sem gravar | Pendente; código de pedido exato e tile IDs não fechados |
| 6 — Camada embarcada | Startup, clocks, portas, tarefas/tiles, ULPI/USB, descritores e drivers | Build de alvo separado, orçamento de SRAM/temporização e revisão de interfaces | Depende das etapas 1, 2 e 5 |
| 7 — Boot e recuperação | Delimitar bootloader, flash, OTP e rota verificável de retorno | Backup/alternativa de recuperação documentada e validada; limites conhecidos | Bloqueio para gravação: sem backup integral e sem recuperação comprovada |
| 8 — Validação no alvo | Primeiro build de bancada, depois controles, música e testes prolongados | Enumeração estável, pads/LEDs/display corretos, recuperação e reconexão verificadas | Apenas após critérios anteriores; não é a próxima ação |

As etapas 5–7 podem receber pesquisa offline em paralelo conceitual, mas não dependem de novos equipamentos nesta fase. Se uma prova exigir acesso físico indisponível, registrar a lacuna e avançar no que é independente dela. Não repetir comandos DFU desconhecidos para tentar contornar a falta de backup.

## Backlog imediato

- [x] Validar o pacote público em uma pasta limpa, sem presets/firmware/capturas locais: build, 45 controles e testes offline conferidos na publicação inicial.
- [ ] Criar contratos de dados para amostra de pad, evento musical, quadro de LEDs e atualização de display.
- [ ] Extrair o núcleo C portável dos modelos já validados; começar por encoder e PWM.
- [ ] Definir fixtures sintéticas e físicas mínimas com proveniência, sem incluir bytes de executáveis NI.
- [ ] Definir detector de ataque com histerese e janela de pico antes de escolher curva de velocity.
- [ ] Capturar batidas leves e fortes dos demais pads em ensaios delimitados e registrar falhas de contagem.
- [ ] Investigar toolchain XS1 L2 em fontes oficiais e testar um build mínimo local, sem acesso ao alvo.
- [ ] Consolidar matriz de inicialização/clock/tile e a lista exata de incógnitas do boot.

## Como medir progresso

Cada mudança deve entregar código ou documento reproduzível, evidência, teste adequado e limite explícito. Não usar percentuais genéricos de firmware concluída: completar o protocolo de LEDs não resolve USB, startup ou recuperação. Capturas manuais dependem de instruções curtas e confirmação do operador. Ensaios de força manual não comprovam ganho de sensibilidade entre pads ou antes/depois de limpeza.

## O que não está autorizado automaticamente por este plano

Publicação inicial deste repositório foi solicitada pelo usuário. Esse fato não autoriza futuras gravações da flash, alteração de OTP, apagamento de firmware, troca de drivers ou reinício de todos os dispositivos USB. A CI e os testes padrão devem permanecer offline. Mudanças na integração existente precisam preservar o projeto musical e o estado do serviço NI.
