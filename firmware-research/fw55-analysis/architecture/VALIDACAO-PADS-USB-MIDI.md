# Validação dos pads: USB real versus processamento reproduzido

## Resultado físico

Na captura de 05/11/2026, a reprodução gerou **41 mensagens MIDI iguais às 41 recebidas do serviço NI, na mesma ordem**: status, número de nota/CC e valor coincidiram. Foram 6 Note On com velocidade positiva, 6 liberações por Note On de velocidade zero e 29 mensagens CC de pressão.

| Batida reconhecida | Velocidade reproduzida | Velocidade MIDI recebida |
|---|---:|---:|
| 1 | 33 | 33 |
| 2 | 62 | 62 |
| 3 | 40 | 40 |
| 4 | 29 | 29 |
| 5 | 54 | 54 |
| 6 | 59 | 59 |

O usuário realizou uma sequência de batidas leves e fortes no PAD 1. Nem toda batida leve gerou nota: o caminho de pressão pode produzir CC sem um evento de batida acima do limiar. O resultado valida as 6 notas efetivamente emitidas e o fluxo completo de 41 mensagens, não uma contagem de 12 notas.

Captura definitiva: `../physical-check/usb-midi-20261105-133945/`.

- `raw.pcap`: 139.498 reports HID `0x20`, filtrados para o endereço USB da MK1.
- `midi.jsonl`: os 41 eventos WinMM, com relógio de chegada.
- `replay-s1000-live-dispatch-phase12.json`: eventos reproduzidos a partir da captura USB.
- `midi-comparison.json`: comparação de cada mensagem e medidas de tempo.

Foi necessária a reconexão USB e a ativação de MIDI por SHIFT + F1: a captura anterior recebeu as batidas por USB, mas nenhuma mensagem MIDI. Esse primeiro registro foi preservado em `../physical-check/usb-midi-20261105-133207/` e não foi usado para afirmar equivalência MIDI.

## O que foi reconstruído e o que foi emulado

Há duas implementações distintas nesta pesquisa:

1. **Modelo independente em Python do filtro de suavização `0x140155200`.** A recorrência foi reconstruída e comparada com a rotina original emulada.
2. **Oráculo do processador completo.** Executa as instruções x64 originais em memória isolada no Unicorn, incluindo os dois estágios numéricos, detecção de pico, estados e curvas. Apenas alocação, preenchimento de memória e verificação de cookie são substituídos por auxiliares do ambiente emulado. Não executa o serviço nativamente, não escreve no processo NI e não acessa USB.

Portanto o resultado físico valida o caminho identificado e a emulação; **não significa que todos os filtros e estados já tenham uma implementação independente em código-fonte**. O primeiro estágio `0x140151B60` ainda é executado como código original emulado. As sondagens em `filter-reconstruction/spatial-probes.json` não são uma identificação completa de suas equações ou finalidade.

O uso do Unicorn segue sua [documentação oficial de emulação e memória](https://www.unicorn-engine.org/docs/tutorial.html). A dependência foi instalada somente na pasta local `.deps-research`.

## Filtro de suavização independente

São quatro seções de primeira ordem em cascata para cada um dos 16 canais. A ordem selecionada escolhe a saída da seção 1, 2, 3 ou 4; o valor atual é **2**.

Cada seção calcula, com arredondamento float32 em cada operação:

```text
y = a*y_anterior + b*x + b*x_anterior
guardar x + epsilon e y + epsilon
epsilon = float32(1e-18)
```

Coeficientes atuais confirmados no serviço:

```text
a = 0.7756796479225159
b = 0.11216013878583908
```

O parâmetro de corte é `0.08`, a taxa configurada é 1500 amostras/s. Esses coeficientes são compatíveis com uma transformação bilinear de um passa-baixas, com aproximação polinomial da tangente na inicialização. O inicializador independente em `check_filter_coefficients.py` é aproximado: em 24 combinações de taxa/corte, o maior erro de coeficiente foi `3.5763e-7`. Nos parâmetros usados nesta validação, os coeficientes coincidiram exatamente.

Teste da recorrência: quatro ordens, 400 amostras e 16 canais por ordem, incluindo impulso, repouso e entradas aleatórias. O maior erro absoluto foi `9.9872e-19`. Houve diferenças de bits em valores próximos do piso numérico; não foi declarada igualdade bit a bit para todos os estados.

Evidências: `filter-reconstruction/smoothing-verification.json`, `coefficients-verification.json` e `emulated-traces.json`.

## Parâmetros efetivos do serviço

Uma inspeção somente de leitura encontrou um objeto MK1 e validou suas duas vtables antes de ler os parâmetros. Foram examinadas páginas privadas graváveis; somente os campos do processador e as duas curvas foram salvos. Não foi retido um dump genérico de memória.

`filter-reconstruction/live-parameters.json` confirma:

- Executável com o mesmo SHA256 da análise estática.
- Taxa 1500; sensibilidade normalizada 1, correspondente ao valor **1000** em `HKLM\Software\Native Instruments\Controller Settings`.
- Limiares `0.04`, `0.10`, `0.0390625` e `0.175`.
- Ajuste opcional por canal desabilitado.
- Buffer circular com 128 posições.
- Contadores: janela de pico 10 amostras, parâmetros temporais de 2, 8 e 22 amostras nos campos identificados.
- Variante de processamento selecionada: RVA `0x141B10`; despacho matemático 3.
- Curvas de pressão e batida extraídas com seus pontos e inclinações, sem inferir os valores a partir do MIDI final.

O template ativo lido foi **FL Studio - 16 Pads**, curva MIDI **1**, PAD 1 em canal MIDI 1, nota 36, faixa 0–127. A pressão está atribuída ao CC 36 no mesmo canal.

## Por que a fase de pressão precisa ser alinhada

O campo do processador `+0x140` é um **contador periódico**, não um atraso único de inicialização:

```text
contador = (contador + 1) % 38
atualizar pressão quando contador == 0
```

Isso aparece em `0x140141A88–0x140141AA0` e na variante equivalente. Com duas amostras por report, são 19 reports, aproximadamente 25,33 ms entre oportunidades de atualização.

A captura começou com o serviço já rodando; o estado inicial desse relógio não estava no arquivo USB. Sua fase foi obtida pelos timestamps: as 29 mensagens CC caíram em reports cujo índice módulo 19 era 8. Para o recorte reproduzido, isso corresponde a fase inicial 12. **Não foram ajustadas velocidades para obter a coincidência.**

Após alinhar essa fase, a conversão MIDI suprimiu três atualizações que repetiam o mesmo valor inteiro de CC, preservando as 29 efetivamente transmitidas. A implementação do mapeamento correspondente está em `0x140171E80` (`host-midi-dedup.asm`).

As notas já tinham velocidades idênticas antes do alinhamento da pressão.

## Tempo observado

Entre o timestamp USB do report de origem e a chegada ao callback WinMM, para as mensagens correspondentes:

- Mínimo: 0,266 ms.
- Mediana: 0,337 ms.
- Máximo: 0,769 ms.

Isso **não mede latência do toque ao áudio**, nem o atraso total de aquisição e detecção. Mede somente os dois pontos de observação dessa captura.

## Reprodução dos resultados

Na raiz do projeto, com `C:\Python314\python.exe`:

```text
firmware-research/emulate_host_filters.py
firmware-research/reconstruct_smoothing_filter.py
firmware-research/check_filter_coefficients.py
firmware-research/replay_pad_capture.py firmware-research/fw55-analysis/physical-check/usb-midi-20261105-133945 --live-dispatch --pressure-phase 12
firmware-research/compare_pad_midi.py firmware-research/fw55-analysis/physical-check/usb-midi-20261105-133945
```

O processamento em lotes também foi comparado com chamadas individuais: os eventos de 100 reports sintéticos coincidiram exatamente. O replay físico usou 5.365 reports do recorte ativo, preservando todos os reports intermediários.

## Limites e estado final

A equivalência física foi demonstrada para **PAD 1, esse template e sensibilidade 1000**. Ainda faltam testes equivalentes dos outros pads, simultaneidade e mudanças de parâmetros; a tradução independente do primeiro estágio e de toda a máquina de estados também permanece pendente. A emulação depende do executável NI preservado e não é um aplicativo autônomo redistribuível.

Nenhuma firmware foi modificada ou gravada. O serviço NI permaneceu ativo durante a captura válida. O monitor MIDI e a captura USB encerraram automaticamente; o template FL Studio foi preservado.
