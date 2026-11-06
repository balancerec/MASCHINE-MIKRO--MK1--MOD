# Processamento dos pads localizado no serviço NI

**Etapa seguinte concluída:** veja [VALIDACAO-PADS-USB-MIDI.md](VALIDACAO-PADS-USB-MIDI.md). Na captura do PAD 1, 41 mensagens reproduzidas coincidiram com as 41 recebidas por MIDI, após alinhar a fase periódica da pressão. O filtro de suavização também ganhou uma implementação independente; as demais rotinas continuam como oráculo emulado.

## Resultado e alcance

Foi localizado o consumidor do report HID `0x20` na classe da MASCHINE MIKRO MK1, o processamento de suas duas varreduras e as rotinas que aplicam sensibilidade, curvas de batida e curva de velocidade MIDI. Esta é análise estática do executável salvo, sem modificar processos, configurações ou firmware.

Arquivo: `firmware-research/evidence/NIHardwareService.exe`.
SHA256: `88f90c4b378f547508b09f190b4bcb30a35cbc5f5d16a7a0d533267a2c1956d9`.

**Os endereços deste documento são VAs preferenciais do executável x64, base `0x140000000`. Não são offsets da firmware nem endereços de flash.** ASLR pode mudar a base em execução.

## Caminho confirmado da MK1

| Etapa | VA | Evidência |
|---|---|---|
| Entrada de reports da MK1 | `0x140126600` | Slot 78 da vtable `0x1405819C8`, associada por RTTI a `MaschineMikroMK1@SERVER@NHL2@NI` |
| Seleção do report de pads | `0x14012661B–0x140126644` | Lê o ID, subtrai 1, compara com `0x1F` — portanto ID original `0x20`; avança um byte e chama o consumidor |
| Consumidor e seleção da implementação | `0x140100B60` | Prepara registros de eventos e chama uma das duas versões abaixo |
| Processamento principal | `0x140140740` ou `0x140141B10` | Duas varreduras de 16 palavras, máscara `0xFFF`, canal nos bits superiores, buffer circular e geração de eventos |
| Ajuste opcional por canal | `0x1401441A0` | Transformação por trechos e saturação 0–1; retorna a entrada quando o campo `+0x100` está desabilitado |
| Estágios numéricos intermediários | `0x140151B60`, `0x140155200` | Recebem os valores e alimentam o caminho de detecção; equações completas ainda não reconstruídas |
| Curva do valor da batida | `0x140146600` | Interpolação em tabela ordenada do campo `+0x1C8`; chamada no caminho `Pad.Hit.Event` |
| Curva do valor de pressão | `0x1401464E0` | Interpolação em tabela ordenada do campo `+0x1B8`; chamada no caminho `Pad.Pressure.Event` |

As duas versões do processamento **não representam MK1 versus MK2**: o consumidor comum seleciona a versão conforme o bit `0x10` de uma flag global e guarda o ponteiro para chamadas seguintes. Ambas são alcançáveis pelo handler da MK1.

O construtor da MK1 em `0x140108A00` configura **1500** como taxa do processador. A cadeia `0x140108A71 → 0x1400ED0F0 → 0x140143170` inicializa esse processador. Isso concorda com duas varreduras por report e aproximadamente 750 reports/s.

## Decodificação e detecção

Cada palavra é interpretada como:

```text
valor = (palavra & 0xFFF) * float32(1 / 4095)
grupo = palavra >> 14
posição = (palavra >> 12) & 3
canal = grupo * 4 + posição
```

O código percorre os dois bancos e escreve as amostras em um buffer circular de 128 posições, cada posição com 16 floats. Os campos de índice são `+0x110` e `+0x114`, e o buffer fica em `+0x108` do objeto processador.

No caminho principal há limiares, estados por canal, contadores e busca de máximos em uma janela do histórico. Por exemplo, `0x140141200` compara sucessivas amostras com o máximo corrente. O valor de pico alimenta a chamada à curva em `0x1401412B1`.

As referências de diagnóstico no próprio executável distinguem:

- `Pad.Hit.Event`, string em `0x140580398`: tipo de evento **1**.
- `Pad.Pressure.Event`, string em `0x1405803C0`: tipo **4**.
- `Pad.Switch.Event`, string em `0x140580370`: transições com tipos **0** e **3**.

Os registros de saída usam três campos de 32 bits: índice do pad, tipo e valor float. O consumidor reserva até 32 registros e encaminha os resultados por uma chamada virtual do dispositivo em `+0x1D8` (`0x1401183D0`). Esta rotina repassa a um callback em `device+0x248`. A cadeia completa de registro e despacho desse callback ainda não foi resolvida.

## Sensibilidade: fórmula localizada

A chave `Maschine Mikro Pad Sensitivity` é lida no construtor, com fallback **1000**, e encaminhada a `0x1401031F0`. Valores unsigned acima de 1000 são ignorados por essa rotina. Para os demais:

```text
s = clamp(configuração * 0.001, 0, 1)
```

`0x1401587B0` interpola quatro pares de parâmetros. Usando os valores iniciais do construtor, as fórmulas aproximadas são:

| Campo do processador | Fórmula inicial | Uso observado |
|---|---|---|
| `+0x134` | `0.08 - (0.08 - 0.04)*s` | Limiar do caminho de pressão |
| `+0x150` | `0.175 - (0.175 - 0.10)*s` | Entrada na detecção de acionamento |
| `+0x154` | `0.10 - (0.10 - 0.0390625)*s` | Condição de liberação |
| `+0x158` | `0.325 - (0.325 - 0.175)*s` | Comparação do pico para o caminho de batida |

São constantes float32 e nomes semânticos de análise. Os oito extremos também podem ser atualizados por `0x140158850`; portanto esses números **não são uma leitura das configurações atuais do equipamento**. Sensibilidade maior reduz os quatro limiares iniciais. Não é apenas um multiplicador de velocidade.

## Curva de velocidade e montagem MIDI

Na classe `MapHandler@MaschineMikroMK1@NHL2@NI`, o método `0x14016F420` trata os eventos de pads para os mapeamentos. Seu ramo de evento tipo 1:

1. Lê a opção identificada pelo código `0x4D705076`.
2. Aplica `0x140253700` ao valor normalizado da batida.
3. Multiplica por 127, chama `lroundf` e limita a 0–127.
4. Chama `0x14016F1E0`, que aplica o intervalo configurado e monta a mensagem conforme o tipo de atribuição.

Para atribuições de nota, essa última rotina compõe status `0x90 | (canal & 0x0F)`, número de nota e velocidade. Também há caminho de liberação com Note On de velocidade zero. Outros tipos de atribuição seguem ramos próprios; nem todo evento de pad necessariamente vira nota.

Há **duas curvas distintas**: a tabela que transforma a força/pico em valor de batida e a opção posterior de curva MIDI. Não se deve aplicar a curva MIDI diretamente ao ADC e esperar reproduzir todo o comportamento NI.

### Fórmulas da opção de curva MIDI

`0x140253700` limita a entrada `x` a 0–1 e usa a tabela de saltos em `0x140253844`:

| ID | Fórmula recuperada |
|---|---|
| 0 | `1 - [0.9*(1-x)^3 + 0.1*(1-x)]` |
| 1 | `1 - [0.6*(1-x)^3 + 0.4*(1-x)]` |
| 2 | `1 - [0.3*(1-x)^3 + 0.7*(1-x)]` |
| 3 | `x` |
| 4 | `0.3*x^3 + 0.7*x` |
| 5 | `0.6*x^3 + 0.4*x` |
| 6 | `0.9*x^3 + 0.1*x` |
| 7 | `x` |

IDs fora de 0–7 também retornam a entrada limitada. Os nomes exibidos pelo produto ainda não foram associados a esses IDs.

## Evidências e reprodução

- `host-pad-report20.asm`: handler específico da MK1, ao lado dos handlers de outros modelos.
- `host-pad-hid-entry.asm`, `host-pad-dispatch.asm`: consumidor e escolha das duas versões.
- `host-pad-path.asm`: processamento, estados, pico, curvas e inicialização.
- `host-pad-curves.asm`: interpolação das tabelas de pressão e batida.
- `host-mikro-settings.asm`, `host-pad-constructor.asm`: origem da taxa e da sensibilidade.
- `host-pad-sensitivity.asm`, `host-pad-sensitivity-apply.asm`: normalização e aplicação da sensibilidade.
- `host-maphandler/rtti-vtables.json` e `host-maphandler/vtable0-slot06.asm`: classe e método do mapeamento MIDI.
- `host-midi-velocity-curve.asm`, `host-midi-note.asm`: curvas e montagem de mensagens.
- `host-pad-path-verified.json`: âncoras verificadas diretamente no binário.

Reproduzir as verificações: `C:\Python314\python.exe firmware-research/verify_host_pad_path.py` a partir da raiz do projeto. A ferramenta confere o hash, 23 instruções-chave, a entrada da vtable, a constante de normalização, a taxa configurada e os oito destinos da tabela de curvas.

## Limites atuais

Localizamos as rotinas; ainda não temos uma reprodução integral do algoritmo NI. Faltam a reconstrução completa dos estágios numéricos, os parâmetros efetivos em execução, a resolução integral do callback intermediário e uma comparação de entrada bruta versus eventos MIDI durante batidas reais. Os trechos de assembly são janelas de análise e podem conter dados ou início/final de funções vizinhas: não são código-fonte recuperado.
