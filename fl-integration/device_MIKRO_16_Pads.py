# name=MIKRO - 16 Pads
# supportedDevices=Maschine Mikro In
"""Only the 16 pad note numbers reach an instrument. All other MIDI is consumed."""
import time
import channels
import transport
import ui
import patterns
import arrangement
import midi
import plugins

held = {}
repeat = False
next_repeat = 0.0
navigation = 'channels'

def pad_note(number):
    """Match the selected FPC's actual Bank A layout; other instruments stay chromatic."""
    index = selected()
    if index >= 0 and plugins.isValid(index) and plugins.getPluginName(index).lower() == 'fpc':
        note = plugins.getPadInfo(index, -1, 1, number - 36)
        if isinstance(note, int) and 0 <= note <= 127:
            return note
        raise ValueError('FPC: pad sem nota MIDI válida')
    return number

def hint(text):
    ui.setHintMsg('MIKRO: ' + text)

def selected():
    return channels.selectedChannel()

def focus(window):
    ui.showWindow(window)
    ui.setFocused(window)

def command(note, event):
    # Original factory messages, channel 14 in the Controller Editor (zero-based 13).
    if note == 10:
        if transport.isPlaying():
            transport.stop()
        else:
            transport.start()
    elif note == 11:
        transport.stop()
        transport.setSongPos(0)
    elif note == 12:
        transport.record()
    elif note == 13:
        ui.previous()
    elif note == 14:
        ui.next()
    elif note == 15:
        ui.delete()
        hint('ERASE - apagar seleção no editor em foco')
    else:
        transport.globalTransport(note, 1)

def control(note, down):
    global repeat, navigation
    if note == 17:
        repeat = down
        hint('NOTE REPEAT ' + ('ligado (1/16)' if down else 'desligado'))
        return
    if not down:
        return
    if note == 6:
        navigation = 'mixer'
        focus(midi.widMixer)
    elif note == 16:
        ui.enter()
    elif note == 18:
        navigation = 'browser'
        # FL can report the Browser visible while Auto-hide keeps it collapsed.
        ui.setBrowserAutoHide(0)
        focus(midi.widBrowser)
        hint('BROWSE - Browser; encoder navega, ENTER confirma')
    elif note == 19:
        channels.showEditor(selected(), 1)
        hint('SAMPLING - editor do instrumento/sample selecionado')
    elif note == 20:
        navigation = 'channels'
        focus(midi.widChannelRack)
    elif note == 24:
        navigation = 'scenes'
        focus(midi.widPlaylist)
        hint('SCENE - encoder navega marcadores da Playlist')
    elif note == 25:
        navigation = 'patterns'
        focus(midi.widChannelRack)
        hint('PATTERN - encoder seleciona patterns')
    elif note == 26:
        if selected() >= 0 and plugins.isValid(selected()) and plugins.getPluginName(selected()).lower() == 'fpc':
            channels.showEditor(selected(), 1)
            hint('PAD MODE - FPC: 16 pads do banco A')
        else:
            focus(midi.widPianoRoll)
            hint('PAD MODE - 16 notas cromáticas no instrumento selecionado')
    elif note == 27:
        ui.nextWindow()
    elif note == 30:
        channels.soloChannel(selected())
    elif note == 31:
        channels.muteChannel(selected())
    elif note == 33:
        patterns.clonePattern()
        hint('DUPLICATE - pattern duplicado')
    elif note == 34:
        navigation = 'channels'
        focus(midi.widChannelRack)
        hint('SELECT - encoder seleciona canal')
    elif note == 39:
        ui.snapMode(1)
        hint('GRID - próxima resolução de snap')

def OnInit():
    hint('16 pads musicais; todos os demais controles são funções')
    print('MIKRO 16 Pads: init OK')
    print('MIKRO: mapa atual dos 16 pads:', [pad_note(n) for n in range(36, 52)])

def OnDeInit():
    global repeat
    repeat = False
    for source, (channel, note, velocity) in list(held.items()):
        channels.midiNoteOn(channel, note, 0)
    held.clear()

def _route(event):
    global navigation
    event.handled = True  # Fail closed: controls can never fall through to the instrument.
    kind = event.status & 0xF0
    channel = event.status & 0x0F
    number, value = event.data1, event.data2
    if channel == 0 and 36 <= number <= 51 and kind in (0x80, 0x90, 0xA0, 0xB0):
        destination = held[number][1] if number in held else pad_note(number)
        if kind == 0xB0:  # NI Press assignment -> polyphonic pressure, not a second note.
            event.midiId = 0xA0
        elif kind in (0x80, 0x90):
            if kind == 0x90 and value:
                held[number] = (channels.channelNumber(), destination, value)
            else:
                held.pop(number, None)
        event.data1 = destination
        event.handled = False
        return
    if kind in (0x80, 0x90):
        down = kind == 0x90 and value > 0
        if channel == 13 and down:
            command(number, event)
        elif channel == 14:
            control(number, down)
        elif channel == 0 and number in (0, 1, 2) and down:
            ui.enter()  # Encoder push in the factory's base/jog/free pages.
        return
    if kind == 0xB0 and channel in (12, 13):
        delta = value - 64
        if not delta:
            return
        if number == 127 and navigation == 'browser':
            ui.jog(delta)
        elif number == 127 and navigation == 'mixer':
            transport.globalTransport(midi.FPT_TrackJog, delta)
        elif number == 127 and navigation == 'patterns':
            patterns.jumpToPattern(max(1, patterns.patternNumber() + delta))
        elif number == 127 and navigation == 'scenes':
            arrangement.jumpToMarker(1 if delta > 0 else -1, 1)
        elif number == 127:
            index = max(0, min(channels.channelCount()-1, selected()+delta))
            if channels.channelCount():
                channels.selectOneChannel(index)
        else:
            transport.globalTransport(number, delta)

def OnMidiMsg(event):
    try:
        _route(event)
    except Exception as error:
        event.handled = True
        print('MIKRO: função bloqueada com segurança:', error)

def OnIdle():
    global next_repeat
    now = time.monotonic()
    if not repeat or not held or now < next_repeat:
        return
    # getCurrentTempo returns BPM; all FL calls stay on the FL scripting thread.
    import mixer
    bpm = max(1.0, mixer.getCurrentTempo())
    next_repeat = now + 60.0 / bpm / 4
    for source, (channel, note, velocity) in list(held.items()):
        channels.midiNoteOn(channel, note, 0)
        channels.midiNoteOn(channel, note, velocity)

