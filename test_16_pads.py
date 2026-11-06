"""Check the musical/control boundary without touching a live FL project."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

class Module(types.ModuleType):
    def __getattr__(self,name):
        if name.startswith(('wid','FPT_')):return 1
        if name in ('channelCount','patternNumber','channelNumber','selectedChannel'):return lambda *a:1
        return lambda *args:None

for name in ['channels','transport','ui','patterns','arrangement','midi','plugins']:
    sys.modules[name]=Module(name)
spec=importlib.util.spec_from_file_location('mikro',Path(__file__).parent/'fl-integration/device_MIKRO_16_Pads.py')
script=importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)

def event(status,number,value=127):
    return types.SimpleNamespace(status=status,data1=number,data2=value,handled=False,pmeflags=0)

class PadBoundary(unittest.TestCase):
    def setUp(self):
        script.held.clear()

    def test_browse_hardware_message_opens_and_focuses_browser(self):
        calls=[]
        old_show,old_focus,old_jog=script.ui.showWindow,script.ui.setFocused,script.ui.jog
        old_auto_hide=script.ui.setBrowserAutoHide
        script.ui.setBrowserAutoHide=lambda enabled:calls.append(('auto_hide',enabled))
        script.ui.showWindow=lambda window:calls.append(('show',window))
        script.ui.setFocused=lambda window:calls.append(('focus',window))
        script.ui.jog=lambda delta:calls.append(('jog',delta))
        try:
            e=event(0x9E,18);script.OnMidiMsg(e)
            self.assertTrue(e.handled)
            script.OnMidiMsg(event(0xBC,127,65))
            self.assertEqual(calls,[('auto_hide',0),('show',script.midi.widBrowser),('focus',script.midi.widBrowser),('jog',1)])
        finally:
            script.ui.showWindow,script.ui.setFocused,script.ui.jog=old_show,old_focus,old_jog
            script.ui.setBrowserAutoHide=old_auto_hide
            script.navigation='channels'

    def test_fpc_all_pads_use_live_plugin_map_and_release_same_note(self):
        original_valid=script.plugins.isValid
        original_name=script.plugins.getPluginName
        original_info=script.plugins.getPadInfo
        mapping=[36,38,42,46,41,43,45,49,37,39,44,51,54,56,70,75]
        script.plugins.isValid=lambda index:True
        script.plugins.getPluginName=lambda index:'FPC'
        script.plugins.getPadInfo=lambda index,slot,option,pad:mapping[pad]
        try:
            for pad in range(16):
                expected=mapping[pad]
                e=event(0x90,36+pad,83);script.OnMidiMsg(e)
                self.assertEqual(e.data1,expected)
                self.assertEqual(e.data2,83)
                self.assertFalse(e.handled)
                mapping[pad]=(expected+1)%128
                pressure=event(0xB0,36+pad,60);script.OnMidiMsg(pressure)
                self.assertEqual(pressure.data1,expected)
                release=event(0x80,36+pad,0);script.OnMidiMsg(release)
                self.assertEqual(release.data1,expected)
                self.assertFalse(release.handled)
        finally:
            script.plugins.isValid=original_valid
            script.plugins.getPluginName=original_name
            script.plugins.getPadInfo=original_info

    def test_all_16_pads_pass_note_on_and_off(self):
        for note in range(36,52):
            for status in [0x90,0x80]:
                e=event(status,note);script.OnMidiMsg(e)
                self.assertFalse(e.handled,(status,note))

    def test_other_notes_never_reach_instrument(self):
        for channel in range(16):
            for note in range(128):
                if channel==0 and 36<=note<=51:continue
                e=event(0x90|channel,note);script.OnMidiMsg(e)
                self.assertTrue(e.handled,(channel,note))

    def test_pressure_becomes_poly_pressure_not_another_note(self):
        e=event(0xB0,36,72);script.OnMidiMsg(e)
        self.assertEqual(e.midiId,0xA0)
        self.assertFalse(e.handled)

    def test_function_releases_are_consumed(self):
        for channel in [12,13,14]:
            e=event(0x80|channel,10,0);script.OnMidiMsg(e)
            self.assertTrue(e.handled)

    def test_play_works_without_optional_pmeflags(self):
        calls=[]
        old_start=script.transport.start
        old_playing=script.transport.isPlaying
        script.transport.start=lambda:calls.append('start')
        script.transport.isPlaying=lambda:False
        try:
            e=event(0x9D,10)
            del e.pmeflags
            script.OnMidiMsg(e)
            self.assertEqual(calls,['start'])
            self.assertTrue(e.handled)
        finally:
            script.transport.start=old_start
            script.transport.isPlaying=old_playing

if __name__=='__main__':unittest.main()
