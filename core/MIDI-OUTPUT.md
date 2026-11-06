# Saída MIDI: fila e contrato de transporte

`src/mk1_midi.c` implementa codificação MIDI 1.0 de NOTE_ON/OFF, fila limitada e recuperação. Nesta etapa o backend é uma função síncrona fornecida pelo chamador. Os testes usam apenas portas falsas em memória. Não há WinMM, ALSA, porta virtual ou envio ao FL/MK1.

## Mensagens e propriedade das notas

NOTE_ON vira `[0x90 | (canal-1), nota, velocity]`; NOTE_OFF vira `[0x80 | (canal-1), nota, 0]`. Canais são 1–16, notas 0–127 e velocity de ataque 1–127. Pressão, CC, SysEx e outros eventos são rejeitados, não descartados silenciosamente em um lote.

A fila comporta 64 mensagens e recebe lotes de até 32. A submissão normal é atômica. A validação inclui o estado projetado depois da fila atual: não aceita dois ataques sobrepostos para a mesma rota ou uma soltura sem ataque. A camada usa um destino/rotas de notas sob controle exclusivo do aplicativo; não administra vozes compartilhadas com outro produtor.

Um mapa de bits mantém as notas que **podem estar soando**. Aceitação pelo backend não é confirmação do sintetizador ou instrumento. MIDI não fornece aqui ACK da voz: não se promete entrega física exatamente uma vez.

## Resultado do backend

| Retorno | Obrigação do backend / ação da fila |
|---|---|
| `MK1_MIDI_OK` | Mensagem inteira aceita pelo backend. Atualiza o mapa e remove esse item da fila. |
| `MK1_MIDI_RETRY` | Há certeza de que nada foi enviado. Mantém o item para tentar depois; prefixo já aceito não é repetido. |
| `MK1_MIDI_UNCERTAIN` | Pode ter sido enviado. Descarta trabalho ainda pendente, registra possível ataque, invalida a geração do produtor e bloqueia a saída. |
| Outro valor | Tratado como entrega incerta. |

O backend deve retornar em tempo limitado e não chamar novamente a fila durante o callback. O ponteiro dos três bytes vale apenas nessa chamada. Uma API que relata erro sem garantir ausência de envio deve ser classificada como incerta, não como `RETRY`.

## Recuperação

Após o chamador confirmar que o backend foi reparado, `resume` permite apenas a limpeza pendente. São enviados NOTE_OFF individuais para o mapa de possíveis notas. Solturas incertas podem ser repetidas; ataques incertos nunca são reenviados automaticamente. Novos ataques ficam proibidos até terminar a limpeza. A recuperação precisa alcançar o **mesmo destino**: limpar um destino novo não silencia aquele que ficou inacessível.

`recover` inicia explicitamente outra geração e cancela a fila, preservando o mapa de possíveis notas. Reinicializar a estrutura com notas ativas apagaria esse conhecimento; primeiro recuperar e concluir a limpeza. Fechar o processo ou perder acesso permanente ao destino não pode ser resolvido apenas por uma fila em memória.

Um lote com `reset_flags` do adaptador inicia recuperação imediatamente. Seus NOTE_OFF não ficam atrás de ataques antigos ainda não enviados: esses ataques são cancelados. O mapa próprio cobre apenas os ataques que chegaram ao backend ou ficaram incertos.

Se um lote válido exceder a capacidade, `FULL` executa a mesma política de recuperação, em vez de perder uma soltura e continuar tocando trabalho antigo. Esse resultado **altera** o estado e a geração, ao contrário de `INVALID`.

## Protocolo do laço chamador

1. Inicializar a fila e guardar sua geração de saída, distinta da geração de entrada HID.
2. Submeter lotes do stream com esse token; em retorno normal, chamar `pump` com orçamento de 1–64 mensagens.
3. Em `RETRY`, manter o loop/watchdog funcionando e tentar posteriormente com limite de tempo/tentativas escolhido pelo backend.
4. Em `FULL`, `RESET` ou `UNCERTAIN`, parar e reinicializar/rearmar o produtor de amostras. Limpezas desse produtor não devem ser submetidas com um token antigo; a fila já preserva seu próprio conjunto de possíveis notas.
5. Reparar o backend quando necessário, concluir NOTE_OFF pendentes e só então obter a nova geração de saída e reiniciar a entrada com referência quieta.

Nenhuma geração deve ser lida automaticamente de novo para aceitar callbacks antigos como se fossem novos. O proprietário associa o token ao trabalho quando ele é criado. Os testes de replay são sequenciais e não simulam uma fila assíncrona de callbacks do sistema operacional.

`INVALID` preserva estado e indica lote/referência rejeitados. Um callback reconhecidamente antigo é descartado. Uma entrada atual inválida é erro do produtor: parar sua emissão e iniciar recuperação explícita, em vez de ignorar uma possível soltura perdida.

Não há thread, ACK assíncrono, fila persistente, escolha de porta nem sincronização interna. O chamador serializa as operações. `pump` limita número de callbacks, não a duração de uma chamada que bloquear. Transporte real, coordenação do loop e testes ao vivo são a etapa seguinte.

## Validação

Onze testes cobrem bytes/ordem nos 16 canais, prefixos aceitos, RETRY, ataques e solturas incertos, bloqueio, token antigo, overflow, reset do stream, ring buffer e mensagens inválidas. Um teste inclui 2.000 operações com falhas e entregas incertas que podem ou não alcançar o receptor falso. A limpeza final deve zerar o receptor e o mapa.

O teste integrado do watchdog aceita só um dos 16 ataques, interrompe o fluxo e verifica que os outros 15 são cancelados: o backend recebe apenas NOTE_OFF da nota já aceita, sem tocar ataques antigos depois da falha.

`tools/replay_pad_stream.py --midi-simulated` acrescenta essa fila ao caminho completo da captura local. O resumo em `docs/MIDI-OUTPUT-VALIDACAO.json` registra o ensaio; a captura original não acompanha o Git. Parâmetros continuam experimentais e não foram aplicados à MK1/FL.
