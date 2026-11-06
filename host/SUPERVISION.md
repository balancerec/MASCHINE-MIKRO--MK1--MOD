# Leitura e saída supervisionadas

O leitor HID e o backend WinMM podem ficar presos em uma chamada de driver. Agora ficam em processos `spawn` separados; o pai não executa essas chamadas. A saída padrão do runner é **memória**, sem abertura de porta MIDI.

## Entrada

`SupervisedHID` abre uma única interface normal `17CC:1110`, ativa leitura não bloqueante e drena o buffer inicial antes de anunciar READY. Não envia reports, features, comandos DFU ou ações ao serviço NI.

HID20 recebe sequência atribuída no processo leitor e timestamp monotônico após a leitura. Um ring buffer compartilhado tem capacidade fixa; encher o buffer causa falha em vez de sobrescrever/reproduzir dados antigos. O pai usa aquisição não bloqueante dos locks; nunca faz I/O de driver dentro deles. Se um processo morrer segurando um lock, a instância de IPC é descartada, não reutilizada.

`run_session` limita duração, quantidade de relatórios por passagem e idade máxima na fila. Chama o watchdog independentemente de chegar dado. Uma falha, relatório malformado, backlog antigo ou fase de recuperação interrompe o produtor. A parada consome as limpezas do coordenador e fecha o leitor com espera finita, tentando terminar o processo se necessário.

O relógio do detector é o de **processamento no pai**, para não voltar atrás do watermark já avançado pelo watchdog. O timestamp do filho mede a idade da fila, não a latência do sensor/USB. Backlog anterior à leitura no driver não é observável. Compressão temporal e jitter precisam ser avaliados musicalmente; esta camada não calibra os pads.

## Saída

`SupervisedMIDI` abre somente um nome explícito e confere a identidade no processo filho. Cada comando leva um número de requisição; o pai só aceita a resposta correspondente. A chamada de envio não respondida no prazo é entrega incerta. O trabalho antigo é interrompido e o backend fica indisponível até recuperação.

A reabertura usa um processo e IPC novos, preserva a identidade selecionada e é recusada enquanto o processo antigo ainda estiver vivo. Isso evita aceitar uma resposta antiga como se pertencesse à conexão nova. A fila nativa continua responsável pelas possíveis notas e permite apenas NOTE_OFF de limpeza antes de novos ataques.

Os deadlines são de aplicação. A finalização usa duas esperas limitadas de aproximadamente 250 ms, além do prazo da chamada; escalonamento/encerramento pelo SO podem acrescentar atraso. Se o SO não encerrar o processo, o resultado não é considerado limpo e a reabertura é bloqueada. Não há promessa de tempo real, cancelamento físico de mensagens já aceitas ou ACK do sintetizador.

## Runner

```powershell
python tools/run_host.py --library build/core-host/mk1_core.dll --seconds 6 --max-age-us 50000 --attack 120 --release 60 --full-scale 4095 --peak-us 10000 --release-us 10000 --retrigger-us 30000 --max-gap-us 250000 --retry-us 1000000
```

Esse exemplo é um **ensaio** com saída só em memória e parâmetros experimentais. A duração é limitada a 60 segundos. Não é perfil de sensibilidade de produção.

Para habilitar saída real, o código exige conjuntamente `--live`, `--port` com nome exato e `--ni-input-isolated`, que declara a confirmação do operador de que a entrada NI antiga não duplicará notas no FL. Não há fallback para um destino automático. Antes de um ensaio, combinar instrumento/contagem e desativar temporariamente a entrada duplicada. Esta publicação foi verificada sem notas reais; não executar o modo live só por seguir o exemplo.

O runner pode fazer uma tentativa limitada de reabrir o mesmo endpoint apenas para limpeza após uma falha; não reinicia a execução musical automaticamente. Falha de limpeza continua como erro, com rotas possivelmente ativas no resumo. O resumo não prova silêncio físico. O processo principal ainda precisa permanecer operacional para supervisionar os filhos.

## Verificação

- Nove testes com processos reais e dispositivos falsos: dados sequenciados, bloqueio na leitura, startup sem resposta, overflow, formato inválido, envio/RETRY, entrega incerta e envio bloqueado.
- Seis testes do laço com relógio falso: duração, ordem, idade inválida, falha do leitor, limpeza e orçamento de processamento.
- Ensaio real de seis segundos com saída em memória: 4.499 relatórios, idade máxima observada na fila de 20.246 µs, leitor encerrado, zero mensagens MIDI reais e nenhuma nota pendente.
- Abertura/conferência/fechamento real de `MIKRO MOD FL` no processo MIDI separado: sucesso, sem enviar notas.

Resumo em `docs/SUPERVISION-VALIDACAO.json`. Instaladores, executáveis, capturas e logs completos continuam locais. A CI só usa dispositivos falsos. Fontes de contexto: [multiprocessing](https://docs.python.org/3/library/multiprocessing.html) e [relógio monotônico](https://docs.python.org/3/library/time.html#time.monotonic).
