# MIKRO — 16 pads musicais e botões de função

Perfil do FL: **MIKRO - 16 Pads**. Template do Controller Editor: **FL Studio - 16 Pads**. Ambos foram instalados e ativados nesta máquina em 04/11/2026.

Somente os 16 pads físicos enviam música. O template NI envia notas 36–51 no canal 1; o script remapeia cada pad à nota real do banco A do FPC selecionado. Em outros instrumentos, mantém notas cromáticas 36–51. Pressão dos pads é convertida em pressão polifônica; não dispara outra nota. Todas as mensagens dos demais controles são consumidas pelo script.

## Funções dos botões

| Botão físico | Ação no FL |
|---|---|
| PLAY | Reproduzir/parar |
| RESTART | Parar e voltar ao início |
| REC | Armar/desarmar gravação |
| ERASE | Apagar a seleção no editor em foco |
| STEP ◀ / ▶ | Seleção anterior / próxima |
| GRID | Próxima resolução de snap |
| MAIN | Abrir e dar foco ao Mixer; encoder seleciona pistas |
| ENTER | Confirmar |
| BROWSE | Abrir e dar foco ao Browser; encoder navega e ENTER confirma |
| SAMPLING | Editor do instrumento/sample selecionado |
| GROUP | Channel Rack / seleção de instrumentos |
| NOTE REPEAT | Enquanto mantido, repete os pads segurados em 1/16 |
| SCENE | Playlist; encoder passa a navegar marcadores |
| PATTERN | Encoder passa a selecionar patterns |
| PAD MODE | Abrir FPC selecionado; em outros instrumentos, Piano Roll |
| VIEW | Alternar janela |
| DUPLICATE | Duplicar pattern selecionado |
| SELECT | Encoder passa a selecionar canal |
| SOLO | Solo do canal selecionado |
| MUTE | Mute do canal selecionado |
| F1/F2/F3 | Funções contextuais das sete páginas, sem enviar notas ao instrumento |
| NAV / SHIFT / setas de navegação | Controles locais do Controller Editor; não são notas musicais |

São equivalências de fluxo do FL, não uma implementação do sequenciador Maschine. As inscrições secundárias dos pads (UNDO, REDO etc.) ainda não foram implementadas como atalhos SHIFT pelo script; os 16 pads permanecem musicais.

## Validação

O usuário confirmou pads musicais e funções de PLAY, RESTART e MUTE. Em um teste posterior, PLAY revelou uma incompatibilidade real da API 40 do FL: `pmeflags` não existe no objeto recebido. O script foi corrigido para usar `transport.start/stop` diretamente e não depender desse campo. O usuário confirmou novamente que PLAY iniciou a reprodução sem tocar A#0.

Sete testes automatizados verificam todos os 16 pads, todas as outras combinações de notas/canais, pressão, liberação de botões e PLAY sem `pmeflags`. Erros de função são capturados com `handled=True`, evitando que a mensagem seja repassada como nota.

ERASE e DUPLICATE não foram acionados no projeto aberto. As outras equivalências ainda precisam de validação física individual.

## Arquivos

- Fonte do script: `fl-integration/device_MIKRO_16_Pads.py`.
- Instalado em `C:\Users\balancerec\Documents\Image-Line\FL Studio\Settings\Hardware\MIKRO 16 Pads\device_MIKRO_16_Pads.py`.
- Template NI: `docs/templates-ni/FL Studio - 16 Pads.ncmm`.
- Página: template **FL Studio · Produção FPC**; botões de função têm canal/tipo/número bloqueados para evitar atribuição musical acidental.
- O template FL Studio original foi mantido, e o perfil anterior do editor web também permanece disponível.

Para usar sons: selecione um instrumento no Channel Rack, mantenha o serviço NI ativo e a MIKRO em MIDI. Não clique **Conectar USB** na ponte HID enquanto estiver usando o FL/MIDI.

## Produção com FPC

Foi criada uma cópia do projeto aberto: `C:\Users\balancerec\Documents\Image-Line\FL Studio\Projects\grisa\grisa - MIKRO Producao.flp`. O original foi preservado. Os dois canais existentes foram mantidos e um FPC foi adicionado.

O banco A inicial é espelhado em posição física, da esquerda para a direita, de baixo para cima:

| Pads | Sons iniciais | Notas MIDI de destino |
|---|---|---|
| 1–4 | SideStick, Kick Drum, Closed Hat, Tambourine | 37, 36, 42, 54 |
| 5–8 | Snare 1, Snare 2, Open HiHat, Pedal HiHat | 40, 38, 46, 44 |
| 9–12 | Hi Tom, Mid Tom, Lo Tom, Floor Tom | 48, 47, 45, 43 |
| 13–16 | Crash, Lite Crash, Lite Ride, Ride Bell | 49, 55, 51, 53 |

As notas acima foram consultadas na própria instância do FPC pela API do FL, não presumidas a partir de um mapa genérico. O script consulta `plugins.getPadInfo(index, -1, 1, padIndex)` para acompanhar alterações de mapeamento do kit. A força do toque permanece inalterada. Liberação e pressão usam a mesma nota remapeada do início do toque.

O perfil foi recarregado no FL API 40, sem erros, com as 16 notas do FPC exibidas no Script output. Testes automatizados cobrem também o mapa dinâmico do FPC e a mensagem física BROWSE com foco e encoder. A validação física desta revisão foi solicitada ao usuário e ainda está pendente.

Referências: [API oficial de MIDI scripting](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm) e [manual do FPC](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/plugins/FPC.htm).

## Correção do BROWSE com Auto-hide
O usuário isolou que BROWSE abre o painel quando oculto no menu View, mas não o expande com Auto-hide ligado. O comando agora chama ui.setBrowserAutoHide(0) antes de abrir e focar o Browser: pressionar BROWSE desativa Auto-hide. O perfil foi recarregado e a função foi executada no console do próprio FL, exibindo o Browser sem erros. Os sete testes passaram, incluindo a ordem de desativar Auto-hide antes de abrir o painel. O registro temporário de cada nota foi removido.

