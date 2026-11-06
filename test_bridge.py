"""Boundary checks against a running loopback bridge; no valid USB writes."""
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE='http://127.0.0.1:8765'

def request(path, body=None, headers=None):
    data=None if body is None else json.dumps(body).encode()
    req=Request(BASE+path,data=data,headers=headers or {})
    try:
        with urlopen(req,timeout=5) as response:
            return response.status,json.load(response)
    except HTTPError as error:
        with error:
            return error.code,json.load(error)

class Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _,session=request('/api/session')
        cls.headers={'X-Mikro-Token':session['token'],'Content-Type':'application/json'}

    def test_status(self):
        code,status=request('/api/status')
        self.assertEqual(code,200)
        self.assertIsInstance(status['connected'],bool)

    def test_no_token_cannot_write(self):
        self.assertEqual(request('/api/leds',{'levels':[0]*60})[0],403)

    def test_foreign_origin_cannot_write(self):
        headers={**self.headers,'Origin':'https://example.org'}
        self.assertEqual(request('/api/leds',{'levels':[0]*60},headers)[0],403)

    def test_foreign_host_is_denied(self):
        self.assertEqual(request('/api/session',headers={'Host':'example.org'})[0],403)

    def test_only_led_range_is_accepted(self):
        for data in [{'levels':[32]*60},{'levels':[-1]*60},{'levels':[True]*60},
                     {'levels':[0]*59},{'levels':[0]*60,'pulses':[60]}]:
            code,_=request('/api/leds',data,self.headers)
            self.assertEqual(code,400)

    def test_source_and_drivers_are_not_served(self):
        for path in ['/mikro_bridge.py','/../LEIA-ME.md','/drivers/anything','/api/raw']:
            self.assertEqual(request(path)[0],404)

if __name__=='__main__':
    unittest.main()
