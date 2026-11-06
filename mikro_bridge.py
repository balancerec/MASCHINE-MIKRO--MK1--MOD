"""Loopback-only MIKRO MK1 LED bridge. No firmware or arbitrary USB commands."""
import atexit
from collections import deque
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.deps'))
import hid

PORT = 8765
ORIGIN = f'http://127.0.0.1:{PORT}'
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()

def ni_service(action):
    if action == 'status':
        result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
            '(Get-Service NIHardwareService).Status.ToString()'], capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        return result.stdout.strip()
    command = 'Stop-Service NIHardwareService' if action == 'stop' else 'Start-Service NIHardwareService'
    subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        "Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile -Command " + command + "' -Wait"],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=90, check=True)
    wanted = 'Stopped' if action == 'stop' else 'Running'
    if ni_service('status') != wanted:
        raise RuntimeError('Não foi possível alterar o serviço NI. Confirme a solicitação do Windows.')

class Hardware:
    def __init__(self):
        self.device = None
        self.restore = '--restore-ni' in sys.argv
        self.info = None
        self.error = None
        self.packet_count = 0
        self.writes = 0
        self.events = deque(maxlen=100)
        self.sequence = 0
        self.previous = {}
        self.levels = [0] * 60
        self.pulses = set()
        self.pad_values = [0] * 16
        self.last_sent = None
        self.running = True
        threading.Thread(target=self.loop, daemon=True).start()

    def event(self, **values):
        self.sequence += 1
        self.events.append({'seq':self.sequence, **values})

    def connect(self):
        if self.device:
            return self.status()
        if ni_service('status') == 'Running':
            self.restore = True
            ni_service('stop')
        device = hid.device()
        try:
            devices = hid.enumerate(0x17cc, 0x1110)
            if len(devices) != 1:
                raise RuntimeError('Conecte uma única MASCHINE MIKRO MK1 ao USB.')
            device.open_path(devices[0]['path'])
            device.set_nonblocking(1)
            descriptor = bytes(device.get_report_descriptor())
            # Measured output report: ID 0x80, 60 8-bit fields, logical maximum 31.
            if bytes.fromhex('8580') not in descriptor or bytes.fromhex('7508953c9102') not in descriptor:
                raise RuntimeError('Descritor de LEDs diferente da MK1 verificada. Escrita bloqueada.')
            self.info = {k:devices[0][k] for k in ['product_string','serial_number','release_number']}
            self.device = device
            self.error = None
            self.last_sent = None
            self.previous = {}
        except Exception:
            device.close()
            if self.restore:
                ni_service('start')
                self.restore = False
            raise
        return self.status()

    def status(self):
        return {'connected':bool(self.device),'device':self.info,'error':self.error,
                'packets':self.packet_count,'writes':self.writes,'events':list(self.events),
                'leds':self.levels,'input_verified':any(e['type']=='input' for e in self.events),
                'ni_paused':self.restore}

    def display_settings(self, changes=None):
        if changes is not None:
            if not isinstance(changes,dict) or not changes or set(changes)-{'brightness','contrast','inverted'}:
                raise ValueError('Use brilho, contraste ou inversão do display.')
            for key,value in changes.items():
                if key=='inverted':
                    if type(value)!=bool:raise ValueError('Inversão deve ser booleana.')
                elif type(value)!=int or not 0<=value<=100:
                    raise ValueError('Brilho e contraste devem estar entre 0 e 100.')
            if not self.device:
                raise RuntimeError('Conecte o USB para aplicar ajustes; o serviço NI será pausado.')
        device=self.device
        temporary=device is None
        if temporary:
            devices=hid.enumerate(0x17cc,0x1110)
            if len(devices)!=1 or devices[0].get('serial_number')!='52569932':
                raise RuntimeError('MK1 calibrada não encontrada.')
            device=hid.device()
        try:
            if temporary:device.open_path(devices[0]['path'])
            before=bytes(device.get_feature_report(0xf8,11))
            if len(before)!=11 or before[0]!=0xf8 or before[8]>100 or before[9]>100 or before[10] not in (0,1):
                raise RuntimeError('Configuração F8 inesperada. Escrita bloqueada.')
            after=before
            if changes is not None:
                target=bytearray(before)
                for key,offset in [('brightness',8),('contrast',9),('inverted',10)]:
                    if key in changes:target[offset]=int(changes[key])
                try:
                    if device.send_feature_report(bytes(target))!=11:raise OSError('Envio F8 incompleto.')
                    after=bytes(device.get_feature_report(0xf8,11))
                    if after!=bytes(target):raise OSError('Leitura do display diverge do ajuste solicitado.')
                except Exception:
                    device.send_feature_report(before)
                    raise
            return {'brightness':after[8],'contrast':after[9],'inverted':bool(after[10]),
                    'verified':True,'source':'hardware-f8','persisted':False}
        finally:
            if temporary:device.close()

    def apply(self, levels, pulses):
        if not isinstance(levels,list) or len(levels)!=60 or any(type(x)!=int or not 0<=x<=31 for x in levels):
            raise ValueError('Esperados 60 níveis de LED entre 0 e 31.')
        if not isinstance(pulses,list) or any(type(x)!=int or not 0<=x<60 for x in pulses):
            raise ValueError('Índices de pulso inválidos.')
        if not self.device:
            raise RuntimeError('Conecte a MK1 primeiro.')
        self.levels = levels.copy()
        self.pulses = set(pulses)
        self.flush()
        return {'accepted':True,'writes':self.writes}

    def flush(self):
        data = self.levels.copy()
        if int(time.monotonic()*2)%2:
            for index in self.pulses:
                data[index]=0
        packet = bytes([0x80]+data)
        if packet != self.last_sent:
            size = self.device.write(packet)
            if size < len(packet):
                raise OSError('Escrita HID incompleta.')
            self.last_sent = packet
            self.writes += 1

    def disconnect(self):
        if self.device:
            try:
                self.device.write(bytes([0x80]+[0]*60))
            finally:
                self.device.close()
                self.device = None
                self.pulses.clear()
                self.last_sent = None
        if self.restore:
            ni_service('start')
            self.restore = False
        return self.status()

    def loop(self):
        while self.running:
            with LOCK:
                if self.device:
                    try:
                        self.flush()
                        for _ in range(100):
                            packet = self.device.read(1024)
                            if not packet:
                                break
                            self.packet_count += 1
                            report = packet[0]
                            if self.previous.get(report)!=packet:
                                previous = self.previous.get(report)
                                self.previous[report]=packet
                                if previous is not None:
                                    self.event(type='input',report=report,bytes=packet,
                                        changed=[i for i,(a,b) in enumerate(zip(previous,packet)) if a!=b])
                    except Exception as error:
                        self.error = str(error)
                        try:
                            self.device.close()
                        except Exception:
                            pass
                        self.device = None
                        self.pulses.clear()
            time.sleep(.01)

HW = Hardware()

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        if len(args)>1 and args[1]=='200':
            return
        super().log_message(format, *args)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(ROOT/'control-studio'/'dist'),**kwargs)

    def allowed(self):
        return self.headers.get('Host')==f'127.0.0.1:{PORT}' and self.headers.get('Origin',ORIGIN)==ORIGIN

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'")
        super().end_headers()

    def reply(self, status, data):
        blob=json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self):
        if not self.allowed():
            return self.reply(403,{'error':'Origem não autorizada'})
        path=urlsplit(self.path).path
        if path=='/api/session':
            return self.reply(200,{'token':TOKEN})
        if path=='/api/status':
            with LOCK:
                return self.reply(200,HW.status())
        if path=='/api/display':
            try:
                with LOCK:return self.reply(200,HW.display_settings())
            except Exception as error:return self.reply(503,{'error':str(error)})
        if path.startswith('/api/'):
            return self.reply(404,{'error':'Endpoint inexistente'})
        preset_files=ROOT/'control-studio/dist/presets'
        if path.startswith('/presets/'):
            from urllib.parse import unquote
            filename=unquote(path[len('/presets/'):])
            if '/' in filename or '\\' in filename or filename in ('.','..') or not (preset_files/filename).is_file() or Path(filename).suffix not in ('.json','.ncmm'):
                return self.reply(404,{'error':'Preset inexistente'})
            return super().do_GET()
        if path not in ['/', '/index.html','/app.js','/hardware.js','/display.js','/presets.js','/style.css','/hardware.css','/fl-studio.js','/fl-template.json','/physical-controls.js','/calibration.js','/physical-calibration.json']:
            return self.reply(404,{'error':'Arquivo inexistente'})
        return super().do_GET()

    def do_POST(self):
        if not self.allowed() or not secrets.compare_digest(self.headers.get('X-Mikro-Token',''),TOKEN):
            return self.reply(403,{'error':'Sessão não autorizada'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16384:
                raise ValueError('Tamanho de requisição inválido')
            data=json.loads(self.rfile.read(size))
            path=urlsplit(self.path).path
            with LOCK:
                if path=='/api/connect':
                    result=HW.connect()
                elif path=='/api/disconnect':
                    result=HW.disconnect()
                elif path=='/api/leds':
                    result=HW.apply(data.get('levels'),data.get('pulses',[]))
                elif path=='/api/display':
                    result=HW.display_settings(data)
                else:
                    return self.reply(404,{'error':'Endpoint inexistente'})
            self.reply(200,result)
        except (ValueError,TypeError) as error:
            self.reply(400,{'error':str(error)})
        except Exception as error:
            self.reply(503,{'error':str(error)})

def cleanup():
    HW.running=False
    with LOCK:
        HW.disconnect()

atexit.register(cleanup)
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    print('MIKRO bridge: '+ORIGIN,flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
