# Núcleo C portável — primeira entrega

Biblioteca C99 sem alocação dinâmica, USB, HTTP, chamadas Windows, temporização real ou saída MIDI. O código compila no **host**; não é build XMOS nem imagem gravável.

## Implementado

- Encoder bruto: passos, armação, rejeição de retorno repetido e contadores modulares, conforme o modelo Python.
- Encoder HID01: posição de quatro bits, clique, referência inicial e salto ambíguo de oito passos.
- PWM de 64 posições: saturação individual, máscara de cinco bits em bloco, retenção da máscara durante o ciclo, próxima fase, overflow de ticks e ordem serial dos oito bytes.
- HID20: 32 amostras de 12 bits com tags de canal e duas varreduras; validação de canais únicos em cada varredura.
- [Detector experimental dos pads](PAD-DETECTOR.md): ataque, janela de pico, velocity linear, histerese, soltura e limpeza explícita de notas.
- [Adaptador do fluxo](PAD-STREAM.md): roteamento dos 16 canais, geração de sessão, sequência, watchdog e limpeza em falhas, ainda sem transporte MIDI.

O detector produz eventos de nota em memória. Ainda não há pressão contínua, serializador MIDI, integração ao vivo do detector ou driver de display.

## Build padrão

Requer CMake, compilador C e Python:

```powershell
cmake -S . -B build/native
cmake --build build/native --config Release
ctest --test-dir build/native -C Release --output-on-failure
```

O build produz uma biblioteca estática, uma compartilhada para comparar com Python e um executável de testes. A CI testa Windows e Linux. Não precisa da FW55, presets, capturas privadas ou equipamento.

Alternativa direta com GCC/Clang: `python tools/test_core.py --cc gcc`.

No Windows original não havia compilador C disponível. Foi usada uma cópia local opcional de [Zig, que oferece compilação C](https://ziglang.org/learn/overview/), versão 0.14.1, obtida do fornecedor e verificada por SHA-256:

```powershell
python tools/fetch_host_compiler.py
python tools/test_core.py --cc .tools/zig-x86_64-windows-0.14.1/zig.exe --zig
```

O download explícito fica em `.tools/`, ignorado pelo Git, e não instala driver ou acessa a MK1. URL/hash estão no script; origem: `https://ziglang.org/download/index.json`. Não é a toolchain XMOS.

## Contratos

`include/mk1_core.h` define as assinaturas. Estruturas são objetos C em memória, **não** pacotes USB nem uma ABI estável. Os testes ctypes declaram a ABI do build host; a camada embarcada deve usar o cabeçalho nativo.

| Dado | Significado |
|---|---|
| `mk1_pad_sample` | tick do adaptador, ADC 0–4095, canal 0–15 e varredura 0/1; canal não é número físico do pad |
| `mk1_control_event` | contrato proposto de nota/pressão/botão/encoder; sem emissão MIDI |
| `mk1_led_frame` | oito bytes internos; não é o relatório HID de 60 estados |
| `mk1_display_update` | retângulo em colunas/páginas e bitmap emprestado; driver pendente |

Ponteiros devem apontar a buffers válidos nos tamanhos declarados; entrada e saída não devem se sobrepor. Falhas detectadas de ponteiro nulo, tamanho, ID ou limites retornam zero sem alterar estado/saída. O chamador serializa o acesso a cada estado; não há sincronização interna.

Ticks são modulares de 32 bits, sem frequência física presumida. A posição bruta do encoder tem oito bits; HID tem quatro. Saltos HID de oito passos são marcados ambíguos; movimentos maiores podem sofrer alias e também não são recuperáveis. O adaptador reinicializa a referência em reconexões/lacunas.

No PWM, mudanças durante o ciclo não reabilitam imediatamente bits já limpos. A aritmética modular do modelo é preservada. O núcleo calcula o próximo prazo; não o agenda nem produz sinais elétricos.

## Verificação

`tests/compare_models.py` compara a biblioteca compilada com os modelos Python existentes. A comparação é **C versus modelos**, não emulação da firmware inteira.

Cobertura: estados do encoder, overflow, sequências aleatórias, 339 cenários PWM com alterações no ciclo, 256 pares de posições HID, fixture física de dez detentes/dois cliques e relatórios de pads sintéticos com canais permutados. `tests/test_core.c` verifica contratos de erro, preservação de saída, amostras e overflow de prazo. Isso não valida eletrônica, força física, latência USB ou boot XMOS.
