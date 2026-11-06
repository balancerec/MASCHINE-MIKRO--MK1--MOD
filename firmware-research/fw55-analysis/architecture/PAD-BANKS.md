# Pads da MK1: dois bancos e processamento

**Atualização:** o consumidor HID e as rotinas de sensibilidade, batida e curva MIDI foram localizados posteriormente. Veja [PROCESSAMENTO-PADS-NI.md](PROCESSAMENTO-PADS-NI.md). O histórico abaixo descreve o estado anterior dessa investigação.

Análise offline da FW55 e da captura já realizada. Nenhuma alteração de firmware ou acesso ao dispositivo nesta etapa. Endereços da firmware abaixo são offsets de arquivo, não endereços absolutos de RAM.

## Resultado

A rotina de aquisição em `0x6830` realiza duas varreduras consecutivas da mesma sequência de 16 canais. No caminho identificado, o índice do banco seleciona o destino no buffer; não seleciona outra porta ou circuito de aquisição. Isso não determina a construção física dos sensores.

O seletor em `0x6820` usa a tabela:

`0, 1, 8, 9, 2, 3, 10, 11, 4, 5, 12, 13, 6, 7, 14, 15`

Para ambos os bancos, o código usa o mesmo seletor, as mesmas leituras de portas, inversão da ordem dos bits (`BITREV`) e máscara de 12 bits. O canal é incorporado aos quatro bits superiores da palavra de 16 bits. O segundo banco ocupa mais 32 bytes; o conjunto contém 64 bytes de amostras.

Pseudocódigo descritivo, sem representar literalmente todas as instruções:

```text
para banco em 0..1:
    para canal em 0..15:
        selecionar entrada pela tabela
        aguardar aquisição
        valor = reconstruir leitura das portas & 0xFFF
        buffer[banco][canal] = valor | (canal << 12)
    avançar referência temporal em 66.666 ticks
enviar conjunto das duas varreduras
```

O caminho identificado recebe esse conjunto em `0x916` e transmite o report HID `0x20` com 64 bytes em `0x444`. Não foi identificada conversão para notas ou velocidade MIDI nesse caminho. Isso não prova ausência de processamento em outras rotinas.

## Comparação com o PAD 1 real

Fonte: `../physical-check/pad1-capture.jsonl`; métricas reproduzíveis com `../../analyze_pad_banks.py`, registradas em `pad-bank-comparison.json`.

| Medida | Resultado |
|---|---:|
| Reports alterados armazenados | 6.471 |
| Linhas ativas, limiar 100 | 5.572 |
| Canal identificado nos dois bancos | 12 |
| Pico banco 0 / banco 1 | 1.327 / 1.330 |
| Correlação entre bancos no mesmo report | 0,9814 |
| Erro RMS comparando banco 1 com banco 0 | 55,31 |
| Erro RMS usando interpolação de meio passo do banco 0 | 33,19 |

A melhora com interpolação é compatível com o banco 1 sendo uma leitura posterior. Não mede exatamente o intervalo e não estabelece a dinâmica de todos os pads: esta captura cobre somente o PAD 1 e armazena alterações com timestamps em milissegundos.

O incremento de timer é 66.666 ticks por varredura. Usando a referência de 100.000.000 encontrada na imagem como frequência desse timer, a previsão é aproximadamente 666,66 microssegundos por varredura e 750,01 reports por segundo. A contagem da captura é aproximadamente 750,31 reports por segundo. A concordância apoia a interpretação; não equivale a uma medição precisa do clock.

## Investigação no computador

Foi feita inspeção estática de `NIHardwareService.exe`, SHA256 `88f90c4b378f547508b09f190b4bcb30a35cbc5f5d16a7a0d533267a2c1956d9`.

O RTTI permite associar tabelas virtuais às classes `PadGroup` da MK1 e `MaschineMikroMK1`. Os inventários e trechos de assembly estão em `host-padgroup/` e `host-device/`, reproduzíveis com `../../inspect_host_padgroup.py`. São candidatos: métodos podem ser herdados, as janelas de desmontagem são limitadas e o nome da classe não fornece a função semântica de cada método.

Foram encontradas referências textuais a sensibilidade e curvas de velocidade. Ainda não foi localizada a rotina que converte as leituras brutas em eventos MIDI. Um método inspecionado, VA `0x1401359F0`, trata mensagens MIDI; isso não o identifica como decodificador dos valores ADC.

## O que falta

1. Localizar no serviço NI o consumidor do report HID `0x20` e acompanhar seus callbacks.
2. Identificar limiar, detecção do pico, rejeição de repetição e curva de velocidade, caso estejam nesse caminho.
3. Comparar a implementação encontrada com capturas simultâneas de valores brutos e MIDI em batidas leves e fortes.

O próximo alvo é o caminho de entrada HID do serviço, incluindo `MaschineHIDController` e `PadControlImplementation`. Não há, até aqui, algoritmo de velocidade recuperado nem firmware modificada.
