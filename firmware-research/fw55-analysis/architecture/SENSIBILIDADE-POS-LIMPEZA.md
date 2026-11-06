# PAD 1 após limpeza: medição inicial

Captura passiva `physical-check/pad-sensitivity-20261105-212957`, 05/11/2026. Foram recebidos 48.355 relatórios de amostras, sem escritas HID e sem alteração do serviço NI. Os três cliques de encerramento de fase foram recebidos.

| Etapa | Relatórios | Grupos de pulsos do PAD 1 | Faixa de picos de 12 bits |
|---|---:|---:|---:|
| Antes do primeiro clique | 37.843 | 10 | 526–1.236 |
| Leves, conforme instrução da etapa | 6.136 | 8 | 1.279–2.189 |
| Fortes, conforme instrução da etapa | 4.376 | 8 | 2.770–3.449 |

O PAD 1 corresponde ao canal 12. O agrupamento diagnóstico usa valores acima de 100 e intervalo maior que 150 ms para separar grupos; isso não prova que cada grupo seja uma batida física. Foram solicitadas seis batidas por etapa, mas apareceram oito grupos em cada etapa de batidas.

O trecho final de dez segundos antes do primeiro clique, excluindo os últimos 500 ms próximos ao marcador, apresentou máximo zero em todos os canais. Os pulsos anteriores da mesma fase impedem usar sua estatística global como ruído de repouso. Houve também atividade no canal 13, correspondente ao PAD 2, com pico 999 no conjunto da captura. Não é possível determinar apenas desses dados se foi toque, transmissão mecânica ou outra causa.

As etapas leve e forte ficaram separadas em amplitude e nenhuma amostra atingiu 4095. Isso mostra resposta graduada ao teste; não quantifica a melhora pela limpeza, pois não há ensaio equivalente controlado anterior. Os picos históricos de outras calibrações não são uma comparação de força padronizada.

Não foi aplicada curva de velocity, limiar de disparo ou compensação de interferência à página ou ao FL. O limiar de realce visual existente na página continua sendo uma função distinta do processamento musical. Faltam amostras validadas de todos os 16 pads e a identificação da atividade vizinha para uma calibração global.

Análise reproduzível: `analyze_pad_sensitivity.py firmware-research/fw55-analysis/physical-check/pad-sensitivity-20261105-212957`. Resultados detalhados em `analysis.json` na pasta da captura. A leitura original foi preservada.

## Repetição controlada: seis batidas centrais

A captura `physical-check/pad-sensitivity-20261105-213439` completou as duas etapas delimitadas pelo encoder, sem escrita no dispositivo. Foram 29.559 relatórios em repouso e 8.721 na etapa de batidas.

Em todo o repouso, os 16 canais ficaram em zero. Na etapa ativa, apareceram exatamente seis grupos no canal 12, com picos `2558, 2931, 3049, 3220, 3267, 3512`. Todos os outros 15 canais permaneceram em zero, inclusive o canal 13/PAD 2. Não houve amostras em 4095.

Portanto, a ocorrência isolada anterior no PAD 2 não se repetiu neste ensaio. Isso não identifica a causa anterior nem prova ausência de transmissão entre pads em outras forças, posições ou combinações. Não há evidência neste teste que justifique aplicar compensação de interferência entre pads.

A medição valida seis respostas isoladas do PAD 1 às batidas centrais firmes. Ainda não fecha uma curva de velocity global: faltam uma série leve com contagem validada e a medição dos demais pads. Os limiares musicais do FL e as configurações da página permanecem inalterados. Evidências: `neighbor-analysis.json` e `quality.json` na pasta dessa captura.

## Quatro cantos: PAD 1, PAD 4, PAD 13 e PAD 16

Captura `physical-check/pad-sensitivity-20261105-213841`, com cinco marcadores recebidos e 40.969 relatórios. Analisador: `analyze_pad_corners.py`; resultado estruturado: `corner-analysis.json` nessa pasta.

| Pad | Canal físico calibrado | Respostas agrupadas | Picos | Mediana dos picos |
|---|---:|---:|---:|---:|
| 1 | 12 | 6 | 2792–3141 | 3059,5 |
| 4 | 15 | 6 | 2982–3489 | 3250 |
| 13 | 0 | 6 | 3043–3343 | 3216,5 |
| 16 | 3 | 6 | 3428–3567 | 3538 |

Não houve saturação. Nas etapas de batidas não apareceu atividade acima do limiar diagnóstico 100 em nenhum outro pad. O repouso apresentou máximo 1 no canal 0 e zero nos demais. Assim, os quatro cantos responderam às seis batidas previstas sem pulsos extras ou atividade vizinha acima desse limiar.

O PAD 16 apresentou picos maiores neste ensaio manual; isso não demonstra uma diferença de sensibilidade, pois a força aplicada não foi padronizada. Não aplicar ganhos relativos a partir dessas medianas. O teste não mede força mínima de disparo, velocity MIDI nem os doze pads restantes. Não houve alteração dos parâmetros da página ou do FL.
