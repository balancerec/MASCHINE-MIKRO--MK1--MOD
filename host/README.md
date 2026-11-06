# Backend Windows e coordenador host

`mk1_host/` contém uma ligação ctypes validada por versão/tamanho da ABI, backend WinMM com destino explícito, coordenador serializado e receptor em memória. Importar o pacote não abre MIDI nem USB. Ainda não há leitor HID/laço de produção ligado ao FL em tempo real.

## Preparação realizada na unidade de referência

- loopMIDI 1.0.16.27 obtido no site do autor, instalador com assinatura digital válida. Instalação concluída sem reinício. Instalador/driver/logs ficam locais, fora do Git.
- O usuário criou a porta `MIKRO MOD FL` e confirmou a entrada habilitada no FL como generic controller.
- WinMM enumerou essa porta. Um teste abriu pelo nome exato, conferiu os dados pelo handle aberto e fechou; **zero chamadas de envio MIDI** nesse teste.
- Não houve notas enviadas ao FL ou ao equipamento para validar esta etapa. A habilitação no FL é confirmação do usuário, não leitura independente de sua configuração.

O loopMIDI precisa continuar em execução para manter as portas. [Fonte do autor](https://www.tobias-erichsen.de/software/loopmidi.html). A página de distribuição descreve Windows 7–10; a instalação/abertura foi observada nesta máquina, sem alegar suporte oficial adicional.

## Enumerar e verificar uma porta sem notas

```powershell
python tools/midi_ports.py
python tools/midi_ports.py --check-port "MIKRO MOD FL"
```

Sem `--check-port`, só enumera. O teste não precisa da biblioteca C. Não usa MIDI Mapper nem porta padrão, rejeita destino inexistente/ambíguo, sintetizadores e a saída `Maschine Mikro Out` nesse fluxo. Índices são consultados novamente; identidade conferida por nome, fabricante, produto, versão e tecnologia. Isso não é GUID persistente e não prova identidade física se um driver recriar um destino com os mesmos metadados.

`WinMMBackend` preserva a identidade na reabertura. `midiOutShortMsg` recebe um DWORD com os três bytes. Sucesso significa aceitação pela API, não ACK do sintetizador; qualquer erro da chamada é classificado conservadoramente como entrega incerta. Ausência de handle produz RETRY sem chamada ao sistema. Uma falha de fechamento preserva o handle para diagnóstico/repetição, em vez de substituí-lo silenciosamente.

Fontes Microsoft: [midiOutOpen](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-midioutopen), [midiOutGetDevCapsW](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-midioutgetdevcapsw), [midiOutShortMsg](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-midioutshortmsg), [midiOutClose](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-midioutclose).

## Ciclo do coordenador

1. Construir `NativeEngine` com a biblioteca compatível e 16 configurações explícitas, indexadas por canal. Não há sensibilidade padrão aplicada.
2. Abrir o destino explicitamente e construir `Coordinator`, com deadline de RETRY e orçamento de pump definidos pelo chamador.
3. Chamar `start(now_us)` e anexar a geração retornada a callbacks da sessão. Sequenciar HID20 na entrada, antes de filas que possam descartar dados.
4. Alimentar `feed(report, now_us, generation, sequence)` e chamar `advance(now_us)` periodicamente, inclusive sem dados e durante falhas. Callbacks de uma sessão antiga são descartados sem renovar o token.
5. Em gap, watchdog ou parada explícita, o produtor para e a fila cancela ataques pendentes. Após limpeza, o estado vira `stopped`; retomar exige `start` explícito e amostra de repouso.
6. Entrega incerta, endpoint alterado, ausência de backend ou RETRY persistente deixam `fault`. Restaurar o mesmo destino e chamar `repair`; isso libera apenas a limpeza. Não há reinício musical automático.
7. Chamar `stop` antes de fechar o backend. Se retornar falso, ainda há falha/limpeza pendente; não tratar isso como prova de silêncio.

O relógio Python é monotônico em microssegundos inteiros sem truncamento; o C recebe os 32 bits baixos. Intervalos que excedem a faixa temporal do núcleo provocam limpeza explícita. Regressão do relógio é erro do chamador. Somente `running` aceita amostras; sessões e gerações de entrada/saída são distintas.

**Limite importante:** o coordenador é síncrono. A Microsoft documenta que `midiOutShortMsg` pode esperar pelo envio. O deadline de RETRY é verificado entre chamadas e não interrompe um driver bloqueado dentro de WinMM. Não há garantia de tempo real ou de recuperação se o processo/laço deixar de executar. Isolamento de I/O bloqueante/supervisão é necessário antes de considerar um laço de produção.

## Testes e replay

Os testes de WinMM usam API falsa até no Windows; a CI nunca abre a porta real. Os testes do coordenador usam biblioteca C e backend falso. Cobrem pressão inicial, sessão antiga, fila/retry, watchdog, duplicações, troca de destino, exceção, intervalo temporal grande e ABI incompatível.

`tools/replay_host.py` reproduz capturas existentes para `MemoryBackend` exclusivamente. A ferramenta não possui opção de porta real. O resultado de 40.969 relatórios foi 24 NOTE_ON e 24 NOTE_OFF, com fila/mapa vazios ao parar. Resumo em `docs/HOST-VALIDACAO.json`; parâmetros são experimentais, sem calibração aplicada.

Próximos passos: leitor HID/laço supervisionado, detecção de backlog, escolha de perfil explícito e ensaio curto combinado com o operador. Antes de usar o caminho próprio, evitar entrada MIDI duplicada do serviço NI no FL. Nenhum ajuste desse caminho existente foi feito nesta etapa.
