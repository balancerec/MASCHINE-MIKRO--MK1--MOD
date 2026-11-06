# MASCHINE MIKRO MK1 + FL Studio 2025

**Perfil atual solicitado pelo usuário:** `MIKRO - 16 Pads`, com template `FL Studio - 16 Pads`. Veja `16-PADS.md`. O restante deste documento registra a integração anterior com o perfil nativo.

Configurado em 04/11/2026 para FL Studio 25.2.5.5319, instalado em `C:\Program Files\Image-Line\FL Studio 2025\FL64.exe`.

## Resultado real

- No FL: entrada **Maschine Mikro In**, habilitada, tipo **Legacy > Native Instruments MASCHINE MIKRO**, porta **0**.
- No FL: saída **Maschine Mikro Out**, porta **0**, vinculada ao mesmo controlador.
- No Controller Editor: template **FL Studio**, curva **Soft 2**, página **System (base)**.
- NIHardwareService em execução; a ponte HID direta liberou o equipamento.
- Após desconectar/reconectar o USB e alternar para MIDI com **SHIFT + F1**, o usuário confirmou: **PLAY iniciou o FL**.
- O teste confirma o transporte PLAY. As outras funções foram preservadas segundo o template, mas não foram todas testadas fisicamente uma a uma.

## Na página

Escolha **FL Studio · NI**. Foram importadas as sete páginas reais:

1. System (base): METRO, WAIT, OVERDUB; encoder LAST TWEAKED.
2. System (jog): +MRK, LOOP REC, STEP EDIT; encoder JOG 2.
3. System (windows): MIXER, STEP SQ, PLAYLIST; encoder WINDOW.
4. System (browser): LEFT, RIGHT, BROWSER; encoder JOG / ENTER.
5. System (edit): CUT, COPY, PASTE; encoder UNDO.
6. System (tempo): NUDGE-, NUDGE+, TAP; encoder TEMPO.
7. Free: BTN 1–3; encoder FREE.

O painel **Ação do controle** separa Hit, Press e clique do encoder. **Todos os parâmetros originais** mostra os campos NI sem perda de informação. O JSON mantém os campos completos em `niSource` e os parâmetros por controle em `ni`.

Os controles fixos e o grupo de pads são compartilhados entre páginas, como no formato NI. O botão **Exportar NI .ncmm** exporta o template completo com as edições das atribuições comuns da página. Para aplicar uma versão editada, importe esse `.ncmm` no Controller Editor; o editor web não grava silenciosamente as edições no serviço NI.

O botão **Usar no FL (MIDI)** libera o HID e restaura o serviço NI. Ele não simula uma conexão entre o navegador e o motor de áudio do FL. A integração real acontece por MIDI usando o suporte nativo do FL.

## Parâmetros preservados

- 88 atribuições originais: controles fixos, páginas do encoder, clique, 16 Hit e 16 Press.
- Canais, notas/CC, comportamento gate/toggle, reaction, default, last e lastExt.
- Atributos de comportamento e modo relativo **offset** do encoder.
- Controles desativados e seus valores armazenados, incluindo SOLO.
- Curva de velocity, handleTransport, wrapmode e handleGroupControls.
- Canais da interface exibidos em 1–16; valores originais 0–15 preservados na origem.
- Pads de Performance Mode: notas 0–15 no canal MIDI 16, na ordem por linhas de cima para baixo. Não são um mapa de bateria GM/FPC.
- Transporte: PLAY nota 10, STOP nota 11 e REC nota 12 no canal MIDI 14.

## Dois modos de uso

**FL/MIDI:** serviço NI ativo, template FL no Controller Editor, SHIFT + F1 no equipamento e perfil nativo no FL. O feedback do controlador é gerenciado por NI/FL.

**HID/LEDs da página:** clique Conectar USB. A ponte pausa o serviço NI e envia os LEDs calibrados diretamente. Enquanto esse modo está ativo, o caminho MIDI oficial do FL fica indisponível. Para voltar, use **Usar no FL (MIDI)** ou **Devolver à NI**; se a unidade não retomar MIDI, reconecte o USB.

## Backups e validação

- `docs/FL-Studio-25-antes.reg`: backup das configurações do FL antes da alteração.
- `docs/templates-ni/MaschineMikro.ncs`: cópia original anterior à integração.
- `docs/templates-ni/FL-Studio-original.ncmm`: template NI original isolado.
- `docs/templates-ni/FL-Studio-2025-factory.ncmm`: template que acompanha esta instalação do FL.
- `docs/templates-ni/FL-Studio-editor.json`: importação completa para a página.
- `docs/templates-ni/FL-Studio-parametros.md`: tabela de todas as atribuições por página.
- A configuração anterior da página foi preservada no armazenamento do navegador, chave `mikro-before-fl-import`.

Exportação da página verificada por `verificar_template_fl.py`: 7 páginas, 32 ações de pad (16 Hit + 16 Press), 7 encoders e 88 atribuições; nenhum campo ou atributo original perdido. Sintaxe JavaScript validada com Node.

Referências oficiais: [configuração NI no FL](https://support.native-instruments.com/support/solutions/articles/69000879800-setting-up-your-maschine-controller-for-host-transport-control-in-fl-studio) e [configurações MIDI do FL](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/envsettings_midi.htm).
