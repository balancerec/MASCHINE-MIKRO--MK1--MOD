# Tradução da rotina de brilho dos LEDs — FW55

Implementação legível: `firmware-research/led_pwm_model.py`. Verificação diferencial: `firmware-research/verify_led_pwm.py`. Ambos funcionam offline e não enviam comandos ao equipamento.

## Em português

A firmware mantém 64 posições internas de brilho. Cada posição aceita um nível entre 0 e 31. Uma máscara de oito bytes contém um bit por posição:

```text
byte = posição // 8
bit  = posição % 8
```

O ciclo começa com os bits habilitados. A rotina desabilita imediatamente os de brilho zero. Depois encontra o menor nível entre os bits ainda habilitados e agenda o próximo evento nesse ponto. Quando chega o evento, desabilita os bits cujo brilho já foi atingido e procura o próximo nível. Na fase 31, reinicia a máscara e começa outro ciclo. O nível 31 permanece habilitado durante todo o ciclo; zero permanece desabilitado.

Isso é PWM por eventos: um nível maior mantém o bit habilitado por uma parcela maior do ciclo. O código não precisa gerar 31 atualizações se só houver poucos níveis diferentes.

## Pseudocódigo equivalente do evento de temporizador

```python
if fase == 31:
    mascara = [0xFF] * 8
    fase_anterior = 0
    limite = 0
else:
    limite = fase

for posição in range(64):
    if brilho[posição] <= limite:
        limpar_bit(mascara, posição)

próxima_fase = menor_brilho_dos_bits_habilitados(ou=31)
prazo += (próxima_fase - fase_anterior) * 0x493E
fase_anterior = próxima_fase
fase = próxima_fase
enviar_bytes(mascara[7], mascara[6], ..., mascara[0])
```

O prazo opera como inteiro de 32 bits, com retorno a zero por overflow. `0x493E` equivale a 18.750 ticks do temporizador por nível. A tradução conserva ticks e não presume uma frequência elétrica medida.

## Exemplo

Para as cinco primeiras posições internas com brilho `[0, 1, 8, 16, 31]`, mantendo as demais em zero:

| Fase processada | Máscara em ordem de memória | Próxima fase |
|---|---|---|
| 0 | `1e 00 00 00 00 00 00 00` | 1 |
| 1 | `1c 00 00 00 00 00 00 00` | 8 |
| 8 | `18 00 00 00 00 00 00 00` | 16 |
| 16 | `10 00 00 00 00 00 00 00` | 31 |
| 31, reinício | `1e 00 00 00 00 00 00 00` | 1 |

Na saída, a ordem dos bytes é invertida: o primeiro quadro acima sai como `00 00 00 00 00 00 00 1e`. O pulso de atualização descrito em `SINAIS-E-SEQUENCIAS.md` ocorre depois dos oito bytes.

Um bit habilitado aqui é um estado lógico da rotina. A polaridade da corrente elétrica do LED não foi medida e não é inferida apenas do valor do bit.

## Duas formas distintas de atualizar brilho

- **Comando individual, `0x7072–0x70C2`:** índice nos 16 bits superiores, valor nos 16 inferiores; índices fora de 0–63 são ignorados. O valor é saturado em 31. Exemplo: 32 vira 31.
- **Atualização em bloco, `0x7120–0x7144`:** aplica `byte & 31` a cada uma das 64 posições. Exemplo: 32 vira 0 e 255 vira 31.

Mudar um nível não religa imediatamente um bit já limpo: ele só volta a ser habilitado quando a máscara reinicia. A tradução mantém esse estado, em vez de recalcular uma máscara nova a cada evento.

Os comandos especiais `0x80000000` e `0x40000000` desviam para outros caminhos; não são níveis de brilho. A recepção desses comandos e a leitura do canal não fazem parte do modelo de PWM.

## Evidência e alcance da validação

O caminho de temporizador começa em `0x6A22`; o reinício está em `0x6A2E–0x6A90`, a comparação dos níveis em `0x6C8A–0x6E54`, a busca do próximo nível em `0x6B7C–0x6C5A` com auxiliares `0x6F28–0x7048`, e o agendamento em `0x6C5C–0x6C70`.

O verificador interpreta apenas esse caminho e seus auxiliares, até antes da chamada de saída. Os bytes das instruções são conferidos contra a imagem FW55 com hash fixado. Seus resultados são comparados com a implementação legível, incluindo níveis extremos, cada posição isolada, padrões mistos, alterações durante o ciclo e overflow do temporizador. Os números finais ficam em `led-pwm-validation.json`.

Isso valida equivalência nesse caminho limitado, não toda a firmware ou o circuito. O mapeamento entre posições internas, relatório HID e controles físicos continua sendo uma camada separada. Não há firmware compilada ou imagem modificada para gravação neste trabalho.
