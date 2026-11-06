"""F8 preservation and failure handling using an isolated fake device."""
import unittest
from unittest.mock import patch
import mikro_bridge as bridge

class Device:
    def __init__(self):self.data=bytes.fromhex('f8800040000100014c2500');self.sent=[];self.mismatch=False
    def get_feature_report(self,*args):return self.data
    def send_feature_report(self,data):
        self.sent.append(data)
        if not self.mismatch or len(self.sent)>1:self.data=bytes(data)
        return len(data)

class Display(unittest.TestCase):
    def setUp(self):
        self.hw=bridge.Hardware.__new__(bridge.Hardware);self.hw.device=Device()
    def test_reads_without_writing(self):
        self.assertEqual(self.hw.display_settings()['brightness'],76)
        self.assertEqual(self.hw.device.sent,[])
    def test_only_requested_bytes_change(self):
        before=self.hw.device.data
        result=self.hw.display_settings({'brightness':63})
        self.assertEqual(result['brightness'],63)
        self.assertEqual(self.hw.device.data[:8],before[:8])
        self.assertEqual(self.hw.device.data[9:],before[9:])
    def test_bad_input_never_writes(self):
        for data in ({'brightness':True},{'contrast':101},{'inverted':1},{'raw':1},[],{}):
            with self.assertRaises(ValueError):self.hw.display_settings(data)
        self.assertEqual(self.hw.device.sent,[])
    def test_readback_mismatch_restores_previous_report(self):
        before=self.hw.device.data;self.hw.device.mismatch=True
        with self.assertRaises(OSError):self.hw.display_settings({'contrast':50})
        self.assertEqual(self.hw.device.sent[-1],before)
    def test_apply_requires_exclusive_bridge_connection(self):
        self.hw.device=None
        with self.assertRaises(RuntimeError):self.hw.display_settings({'brightness':50})

if __name__=='__main__':unittest.main()
