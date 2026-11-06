# Sinais e sequências dos periféricos MK1

Reconstrução offline de 05/11/2026. Base: imagem FW55 normalizada, wrappers e fluxo de registradores do segmento 1. Nenhum acesso USB nem escrita na memória do equipamento.

## Display

O wrapper `0x67A8` passa `8C`, `8A` e `1A` para `0x6570`.

- `8A`: saída dos bytes de comandos e dados gráficos. Em `0x6586`, recebe o comando `0xA3`; em `0x6552`, recebe bytes do bitmap.
- `8C`: vetor de controle. Uma escrita de comando usa o valor `4`; uma escrita de dados usa `6`. Ambas passam depois ao valor `8`. Isso separa uma linha lógica de comando/dados no bit 1; não identifica a ligação física de cada bit restante.
- `1A`: saída com sequência de inicialização baixa, espera, alta, espera, em `0x647C–0x64A8`. Função compatível com reset do LCD; o nome elétrico permanece inferido.

Após sincronizar uma escrita de controle, o código agenda as duas saídas seguintes em `t+9` e `t+25`, ambas com valor `8`. São timestamps relativos de porta, não tempos em segundos. Não se deve atribuir a duração física sem fechar a configuração de clock e a semântica dos buffers.

O protocolo de páginas envia a coluna alta (`0x10 | coluna>>4`), coluna baixa (`coluna & 15`) e página (`0xB0 | página`) antes dos bytes gráficos. A rotina limita a página a 0–7 e a coluna inicial a menos de 128, e recorta a largura ao final da linha. Esse comportamento sustenta o modelo de 128×64 já observado; os comandos, sozinhos, não identificam um modelo único de controlador LCD.

## Pads

O wrapper `0x67BC` passa `8B`, `1J`, `1I`, `1H` e um bloco de clock a `0x6830`.

| Porta | Operação localizada | Interpretação |
|---|---|---|
| 8B | `out` em `0x689E`, com saída da tabela de seleção | Seleção do canal analógico |
| 1J | `setpsc 16` e `in` em `0x68B2/0x68BA` | Entrada serial de aquisição |
| 1I | Associação ao bloco de clock em `0x684E–0x6856` | Sinal de clock, compatível com clock de ADC |
| 1H | Saída 0 antes da leitura e 1 depois, em `0x68B6/0x68C0` | Enquadramento da aquisição, compatível com seleção de ADC |

O código espera `0x258` ticks do temporizador depois de mudar o seletor. A aquisição inicia o bloco de clock, lê a porta e para o bloco. A palavra recebida passa por `BITREV`, máscara `0xFFF` e inclusão do canal nos quatro bits superiores:

```text
amostra = (BITREV32(leitura_serial) & 0xFFF) | (canal << 12)
```

Há dois ciclos de 16 canais por bloco transmitido. Isso não implica 32 pads físicos: são duas varreduras de 16 canais. O componente ADC continua sem identificação; largura de transferência e máscara não bastam para fechar o modelo ou sua ligação elétrica.

## Botões e encoder

O wrapper `0x67DC` fornece o clock e as portas `1L`, `1M`, `1K`. Em `0x63F4`, `1K` recebe uma sequência alta/baixa/alta, com transições agendadas em `t+5` e `t+6`. A leitura de `1M` começa em `t+13` e progride em intervalos de oito unidades de timestamp, preenchendo quatro bytes. `1L` está associado ao bloco de clock.

Isso é compatível com entrada serial de registradores com carga paralela, mas não identifica o CI nem prova sua pinagem. O código compara os bits anteriores e atuais e gera estado pressionado quando o bit lido é zero (`0x63C6–0x63CA`): a interpretação lógica dos botões é ativa em nível baixo. O processamento do encoder e a decisão de emitir mudanças ficam acima dessa leitura; esta reconstrução não substitui o mapa físico calibrado.

## LEDs e iluminação do display

`1N` é passado ao contexto que executa `0x7170`. Esse contexto escreve diretamente nessa porta e implementa PWM: valor 0 mantém saída baixa, valor 100 força alta e valores intermediários comparam a fase com o brilho pedido. A fase usa módulo 101 e o incremento de agendamento é `0x1EF`. Portanto, `1N` pertence à iluminação do display, embora seu argumento seja recebido pelo serviço dos LEDs.

Na transmissão de um quadro serial, `0x71D8`:

1. Coloca `1F` em zero e lê seu timestamp.
2. Envia em `1C` oito bytes, dos índices 7 até 0, com timestamps `t+10, t+18, …, t+66`.
3. Agenda `1F=1` em `t+74` e `1F=0` em `t+75`.

`1E` é associado ao bloco de clock. A função de `1F` é compatível com latch do quadro serial. `1D` é uma saída auxiliar cuja função elétrica completa ainda não foi fechada. O quadro de oito bytes dessa camada não deve ser confundido com o relatório HID de 60 estados de LEDs: há processamento intermediário de brilho e organização dos bits.

## Verificação e continuidade

`reconstruct_signal_roles.py` verifica o hash da firmware e compara 48 instruções citadas com seus bytes na imagem. Também executa 65.536 casos do modelo de empacotamento dos pads e gera exemplos de sequências LCD/LED em `signal-roles.json`. É um modelo limitado da especificação reconstruída, não execução ou emulação do processador XS1, nem validação elétrica.

O avanço concreto é separar dados, controle, seleção, entrada serial e iluminação antes de escrever os drivers. Próximo alvo: reconstruir a conversão dos 64 estados internos de LED para os oito bytes serializados e detalhar a leitura do encoder, preservando as diferenças entre evidência de código e nomes elétricos inferidos.

**Atualização:** a conversão dos níveis internos em máscaras e eventos de brilho foi traduzida em `LEDS-TRADUZIDOS.md` e no módulo `led_pwm_model.py`, com um verificador diferencial limitado ao caminho de temporizador. O encoder continua como trabalho separado.
