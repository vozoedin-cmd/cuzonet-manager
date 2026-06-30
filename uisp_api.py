import requests
import urllib3

# Disable insecure request warnings (UISP often has self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class UISPAPI:
    def __init__(self, url, api_key):
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'x-auth-token': self.api_key,
            'Content-Type': 'application/json'
        }

    def ping(self):
        """Test connection to UISP API"""
        try:
            url = f"{self.base_url}/nms/api/v2.1/devices?count=1"
            response = requests.get(url, headers=self.headers, verify=False, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Error connecting to UISP: {e}")
            return False

    def get_devices(self):
        """Fetch all devices from UISP"""
        try:
            url = f"{self.base_url}/nms/api/v2.1/devices"
            response = requests.get(url, headers=self.headers, verify=False, timeout=15)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error fetching devices from UISP: {e}")
            return []

    def get_cuzonet_sync_data(self):
        """
        Fetches devices and maps them to CuzoNet's Infraestructura model fields.
        Returns a dictionary keyed by IP address or MAC address for easy syncing.
        """
        raw_devices = self.get_devices()
        sync_data = {}
        
        for dev in raw_devices:
            ident = dev.get('identification', {})
            overview = dev.get('overview', {})
            attributes = dev.get('attributes', {})
            ip = dev.get('ipAddress', '')
            mac = ident.get('mac', '')
            
            key = ip if ip else mac
            if not key:
                continue
                
            status = overview.get('status', 'offline')
            online = status in ['active', 'online']
            
            cpu = overview.get('cpu', None)
            ram = overview.get('ram', None)
            temp = overview.get('temperature', None)
            volt = overview.get('voltage', None)
            uptime = overview.get('uptime', None)
            
            firmware = ident.get('firmwareVersion', '')
            model = ident.get('modelName', ident.get('model', ''))
            name = ident.get('name', ident.get('hostname', ''))
            
            location = dev.get('location', {})
            gps = ""
            if location.get('latitude') and location.get('longitude'):
                gps = f"{location['latitude']}, {location['longitude']}"
                
            tx = overview.get('downlinkCapacity', 0) / 1000000 if overview.get('downlinkCapacity') else 0 
            rx = overview.get('uplinkCapacity', 0) / 1000000 if overview.get('uplinkCapacity') else 0
            
            ccq = None
            airmax_quality = None
            if 'airmax' in dev:
                airmax_data = dev['airmax']
                ccq = airmax_data.get('ccq', None)
                airmax_quality = airmax_data.get('quality', None)
            
            sync_data[key] = {
                'uisp_id': ident.get('id', dev.get('id')),
                'mac': mac,
                'nombre': name,
                'modelo': model,
                'estado_online': online,
                'rssi': overview.get('signal', None),
                'ccq': ccq,
                'airmax_quality': airmax_quality,
                'trafico_tx': round(tx, 2),
                'trafico_rx': round(rx, 2),
                'temperatura': temp,
                'cpu': cpu,
                'ram': ram,
                'voltaje': volt,
                'uptime': str(uptime) if uptime else "",
                'gps': gps,
                'firmware': firmware,
                'clientes_conectados': overview.get('stationsCount', 0)
            }
            
        return sync_data

# MOCK VERSION FOR TESTING WITHOUT REAL CREDENTIALS
class MockUISPAPI:
    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key
        
    def ping(self):
        return True
        
    def get_cuzonet_sync_data(self):
        import random
        return {
            '192.168.1.50': {
                'uisp_id': 'mock-id-123',
                'mac': '04:18:D6:XX:XX:XX',
                'nombre': 'Sectorial Norte',
                'modelo': 'LiteBeam 5AC Gen2',
                'estado_online': True,
                'rssi': random.randint(-65, -50),
                'ccq': round(random.uniform(85.0, 100.0), 1),
                'airmax_quality': round(random.uniform(80.0, 99.0), 1),
                'trafico_tx': round(random.uniform(10.0, 50.0), 2),
                'trafico_rx': round(random.uniform(5.0, 20.0), 2),
                'temperatura': round(random.uniform(35.0, 60.0), 1),
                'cpu': round(random.uniform(10.0, 40.0), 1),
                'ram': round(random.uniform(30.0, 60.0), 1),
                'voltaje': 24.1,
                'uptime': '15d 4h 20m',
                'gps': '14.6349, -90.5069',
                'firmware': 'WA.v8.7.1',
                'clientes_conectados': random.randint(5, 25)
            },
            '192.168.1.51': {
                'uisp_id': 'mock-id-456',
                'mac': '04:18:D6:YY:YY:YY',
                'nombre': 'Sectorial Sur',
                'modelo': 'Rocket 5AC Prism',
                'estado_online': True,
                'rssi': random.randint(-70, -60),
                'ccq': round(random.uniform(90.0, 100.0), 1),
                'airmax_quality': round(random.uniform(85.0, 99.0), 1),
                'trafico_tx': round(random.uniform(20.0, 80.0), 2),
                'trafico_rx': round(random.uniform(10.0, 30.0), 2),
                'temperatura': round(random.uniform(40.0, 65.0), 1),
                'cpu': round(random.uniform(15.0, 50.0), 1),
                'ram': round(random.uniform(40.0, 70.0), 1),
                'voltaje': 24.2,
                'uptime': '30d 12h 5m',
                'gps': '14.6349, -90.5069',
                'firmware': 'XC.v8.7.1',
                'clientes_conectados': random.randint(10, 40)
            },
            '192.168.1.60': {
                'uisp_id': 'mock-id-789',
                'mac': '04:18:D6:ZZ:ZZ:ZZ',
                'nombre': 'Estación Cliente Falla',
                'modelo': 'NanoStation Loco M5',
                'estado_online': False,
                'rssi': None,
                'ccq': None,
                'airmax_quality': None,
                'trafico_tx': 0,
                'trafico_rx': 0,
                'temperatura': None,
                'cpu': None,
                'ram': None,
                'voltaje': None,
                'uptime': None,
                'gps': None,
                'firmware': 'XW.v6.3.2',
                'clientes_conectados': 0
            }
        }
