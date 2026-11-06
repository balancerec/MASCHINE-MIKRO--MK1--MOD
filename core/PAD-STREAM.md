# Adaptador do fluxo de pads — host experimental

`src/mk1_stream.c` liga relatórios HID20 ao detector experimental. Contém um estado por canal, combina as duas varreduras pelo máximo e encaminha eventos em memória. Não abre o USB, não cria threads, não emite MIDI e não está ligado ao FL/editor ao vivo.

## Contrato do chamador

1. Inicializar com 16 configurações **indexadas pelo canal ADC**, não pelo número físico. O mapa calibrado fornece a relação. IDs de controle e pares `(canal MIDI, nota)` devem ser únicos; vozes sobrepostas exigiriam outro gerenciador.
2. Chamar `connect`, consumir seus eventos e guardar `generation`. Anexar essa geração a todos os callbacks/quadros dessa sessão.
3. Atribuir uma sequência de 32 bits a cada HID20 quando ele entra no sistema, antes de filas que possam descartar quadros. O relatório não fornece um contador de transporte; perdas anteriores à atribuição não podem ser inferidas dessa sequência.
4. Chamar `frame` com geração, sequência e relógio monotônico de chegada. Identificadores alheios a HID20 são ignorados. O parser exige cada canal uma vez por varredura.
5. Chamar `poll` periodicamente no **mesmo domínio de tempo**, mesmo sem dados ou quando a entrada está falhando. I/O bloqueante sem timeout impediria o watchdog de executar.
6. Consumir cada lote aceito exatamente uma vez e na ordem fornecida. Em desconexão ou reinício, chamar `disconnect`/`connect` e consumir os NOTE_OFF antes de descartar a sessão.

Ponteiros/buffers devem ser válidos e não se sobrepor. O chamador serializa acesso ao estado; ele não deve editar estruturas internas. Reconfiguração requer desconexão com entrega dos eventos pendentes antes de reinicializar.

## Política de falhas

| Situação | Resultado |
|---|---|
| Sequência repetida/antiga, geração anterior, tempo regressivo ou ID diferente | Retorno 0, estado e saída preservados; não consumir um lote antigo como se fosse novo |
| Salto de sequência para frente | NOTE_OFF dos estados ativos, descarte de picos pendentes e nova referência de repouso |
| Intervalo de chegada maior que `max_gap_ticks` | Mesma limpeza; quadro atual passa a ser a referência nova |
| HID20 malformado, dentro da sessão/ordem válida | Limpeza e desconexão; requer `connect` com nova geração |
| Watchdog expira, inclusive antes do primeiro quadro | Limpeza e desconexão; requer nova conexão |
| Reconexão explícita enquanto há notas ativas | NOTE_OFF, nova geração, nova referência de repouso |

Retorno 1 significa operação aceita, inclusive recuperação; `reset_flags` explica a limpeza. Intervalos exatamente iguais ao limite ainda são aceitos. Sequência e ticks seguem aritmética modular; avanço de meia volta ou mais é ambíguo e rejeitado. O relógio de `poll` também vira referência: um quadro atrasado com timestamp anterior ao último poll não pode fazer o tempo voltar.

Depois de qualquer limpeza, sinal alto não vira um novo ataque. É preciso primeiro observar repouso e depois outro cruzamento. Essa escolha pode descartar um toque durante uma interrupção; evita criar uma nota atrasada a partir de sinal antigo.

## Limites dos lotes e memória

Um quadro gera no máximo 32 eventos: NOTE_ON e NOTE_OFF de um toque curto para cada um dos 16 canais. Limpeza gera até 16 NOTE_OFF; como o estado reinicializado exige repouso, não cria novos ataques no quadro da limpeza. Todos os eventos de um canal mantêm sua ordem.

As funções usam cópias locais e só confirmam estado/saída ao terminar, sem heap. Isso preserva a transação em erros detectados, mas usa memória de pilha proporcional aos 16 estados, 32 amostras e lote. O orçamento de pilha/tempo precisa ser medido novamente no futuro alvo XMOS; a compilação host não o comprova.

O watchdog não garante entrega se o chamador parar, não executar `poll` ou perder os lotes. A [fila de saída](MIDI-OUTPUT.md) agora trata ordenação/recuperação em memória com callback síncrono simulado; backend real e coordenação do laço continuam pendentes.

## Verificações

`core/tests/test_pad_stream.py` cobre roteamento por tags, máximo das varreduras, lote máximo, duplicação/reordenação, gaps, watchdog, reconexão, sessão antiga, relatório malformado, relógio regressivo, wrap e rotas inválidas. Um ensaio de 4.000 operações com falhas aleatórias confere balanço NOTE_ON/OFF e consistência dos estados após cada operação aceita.

`tools/replay_pad_stream.py` executa o caminho nativo completo sobre capturas locais, exigindo parâmetros explícitos. O ensaio dos quatro cantos reproduziu seis pares por pad, sem limpeza pendente ao final. Resumo público em `docs/PAD-STREAM-VALIDACAO.json`; a captura bruta não é publicada. Os valores usados são de teste, não calibração aplicada, e o relógio reflete chegada no host, não a latência física do sensor.
