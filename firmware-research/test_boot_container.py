import struct,unittest
from inspect_boot_container import ROOT,BITREV,inspect
class Container(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.raw=(ROOT/'official-firmware/Maschine-Mikro-MK1-FW55.official-payload.bin').read_bytes()
    def test_known_image(self):
        r=inspect(self.raw);self.assertEqual(r['segment_count'],2);self.assertEqual(r['container_version'],1)
        self.assertEqual(r['content_extent'],32196);self.assertEqual(r['padding_bytes'],60)
        self.assertTrue(r['crc_validated'])
        self.assertEqual(r['payload_sha256'],'3cbfb13ff2e884d4eb3a3ec9546121c2e29c2fc42f6189c5d1df9dedccb88003')
    def test_reversible_normalization(self):self.assertEqual(self.raw.translate(BITREV).translate(BITREV),self.raw)
    def test_truncated_image_rejected(self):
        with self.assertRaises(ValueError):inspect(self.raw[:100])
    def test_corrupt_segment_bounds_rejected(self):
        d=bytearray(self.raw.translate(BITREV));struct.pack_into('<I',d,36,0xffffffff)
        with self.assertRaises(ValueError):inspect(bytes(d).translate(BITREV))
    def test_code_mutation_fails_content_crc(self):
        d=bytearray(self.raw);d[500]^=1
        self.assertFalse(inspect(bytes(d))['crc_validated'])
if __name__=='__main__':unittest.main()
