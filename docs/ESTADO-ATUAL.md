# Estado atual — 06/11/2026

Esta é a referência atual; os relatórios em `firmware-research/` conservam detalhes e histórico.

## Observado no equipamento

- MK1 normal `17CC:1110`, FW55 informada pelo equipamento; DFU `1112` observado anteriormente.
- Acesso HID e controles de LEDs, bitmap do LCD, brilho, contraste e inversão validados em ensaios locais.
- Mapas dos 16 pads, botões e endereços dos LEDs calibrados; 52 dos 60 endereços investigados tiveram identificação visível.
- Encoder: dois cliques delimitando dez passos confirmaram dez incrementos para a direita; contador HID módulo 16; push bit 11. Esquerda e alta velocidade ainda sem ensaio físico controlado.
- Quatro cantos, seis batidas firmes cada: PAD1 2792–3141; PAD4 2982–3489; PAD13 3043–3343; PAD16 3428–3567. Sem saturação ou atividade dos outros pads acima de 100; repouso máximo 1.
- A ocorrência anterior isolada de PAD2 durante PAD1 não se repetiu nos ensaios centrais. Não foi aplicada compensação.
- Fotos locais identificaram flash AT25DF021 e USB3318; XMOS L2/C5 compatível com a família XS1-L02A. O código de pedido completo do micro não foi fechado inequivocamente.

## Reconstruído offline

- Payload oficial FW55 de 32.256 bytes, representação por reversão dos bits de cada byte, dois segmentos e checksums legados validados.
- Estrutura de flash compatível com AT25DF021 de 256 KiB, páginas de 256 bytes. Não é prova de conteúdo da flash instalada.
- Serviços de pads, botões, LEDs e LCD localizados; argumentos de portas XS1 traduzidos pela tabela oficial de recursos.
- Encoder: 40.960 comparações de estado e 10.000 amostras sequenciais contra interpretação limitada de 33 instruções.
- PWM LEDs: 13.560 passos comparados em 339 cenários, cobrindo 693 endereços de instrução. É um interpretador limitado, não um emulador completo.
- Boot e caminho DFU do atualizador estudados; upload DFU da unidade retornou zero bytes. CRC correto não comprova aceitação/boot de imagem modificada.

## Implementado no host em C99

`core/` contém encoder bruto, leitura do encoder HID01, PWM de 64 posições e parser HID20 com tags de canal. Sem heap, USB, serviço NI ou emissão MIDI. Contratos de evento musical e atualização LCD declarados, ainda sem processamento/driver.

Build local Windows com Zig cc 0.14.1, avisos tratados como erros. Comparações C/Python: 40.960 passos individuais e 10.000 amostras sequenciais do encoder; 339 cenários/13.560 eventos PWM; 256 pares HID; fixture física de dez passos e dois cliques; 100 relatórios de pads sintéticos. Isso testa equivalência com os modelos, não inicialização no alvo.

O detector próprio experimental em `core/src/mk1_pad.c` acrescenta ataque, janela de pico, velocity linear configurável, histerese, soltura temporizada, bloqueio de novo ataque e limpeza explícita. Oito testes de comportamento cobrem as 3.996 amplitudes sintéticas de pico de 100–4095, sustentação, ruído, configuração inválida, rotas independentes e passagem do temporizador por zero. Não é tradução do processador musical NI.

Replay local de 40.969 relatórios da captura dos quatro cantos: 24 NOTE_ON e 24 NOTE_OFF, seis por pad, sem liberação pendente no flush. Os parâmetros foram de ensaio e não foram aplicados ao equipamento/FL. Resumo público em `PAD-DETECTOR-VALIDACAO.json`; captura original permanece local. Não há integração ao vivo desse detector.

## Lacunas e entregas inexistentes

Sem backup integral da flash, bootloader específico recuperado, OTP lida, ferramenta de recuperação comprovada, toolchain de alvo validado ou firmware própria compilada para XMOS. Sem esquema completo, identificação inequívoca do ADC/controlador LCD ou mapeamento físico de tiles/pinos. O núcleo C e o detector inicial existem no host; pressão contínua, integração MIDI e calibração musical completa dos pads continuam pendentes.

Não há dados padronizados dos 16 pads para curva global de velocity. Os dados pós-limpeza não quantificam melhora sem um ensaio anterior equivalente. O monitor HID da página e o script MIDI do FL são caminhos diferentes; a ponte não substitui o serviço NI como fonte MIDI.

## Onde está o material

Documentação autoral e ferramentas selecionadas são públicas. Firmware, desmontagens completas, fotos da unidade, capturas e executáveis permanecem no ambiente original. Ver `MATERIAIS-E-FONTES.md`. Testes padrão usam mocks ou fixtures reduzidas próprias e não precisam desses arquivos.
