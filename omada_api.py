import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OmadaAPI:
    def __init__(self, url, username, password, site_name='Default'):
        self.base_url = url.rstrip('/')
        self.username = username
        self.password = password
        self.site_name = site_name
        self.session = requests.Session()
        self.session.verify = False
        self.omadac_id = None
        self.token = None
        self.site_id = None

    def login(self):
        # 1. Obtener OmadacId
        res = self.session.get(f"{self.base_url}/api/info", timeout=10)
        res.raise_for_status()
        info = res.json()
        self.omadac_id = info.get('result', {}).get('omadacId')
        
        if not self.omadac_id:
            raise Exception("No se pudo obtener OmadacId. Verifica la URL.")

        # 2. Login
        login_url = f"{self.base_url}/{self.omadac_id}/api/v2/login"
        res = self.session.post(login_url, json={"username": self.username, "password": self.password}, timeout=10)
        res_data = res.json()
        
        if res_data.get('errorCode') != 0:
            raise Exception(f"Login fallido: {res_data.get('msg', 'Credenciales inválidas')}")
            
        self.token = res_data.get('result', {}).get('token')
        self.session.headers.update({"Csrf-Token": self.token})
        
        # 3. Obtener Site ID
        sites_url = f"{self.base_url}/{self.omadac_id}/api/v2/sites?currentPage=1&currentPageSize=50"
        res = self.session.get(sites_url, timeout=10)
        sites_data = res.json()
        
        if sites_data.get('errorCode') != 0:
            raise Exception("No se pudieron cargar los sitios.")
            
        sites = sites_data.get('result', {}).get('data', [])
        for s in sites:
            if s.get('name') == self.site_name:
                self.site_id = s.get('id')
                break
                
        if not self.site_id:
            sitios_disp = ", ".join([s.get('name') for s in sites])
            raise Exception(f"Sitio '{self.site_name}' no encontrado. Sitios disponibles: {sitios_disp}")
            
        return True

    def test_connection(self):
        try:
            self.login()
            return True, "Conexión exitosa a Omada"
        except Exception as e:
            return False, str(e)
            
    def generar_fichas(self, cantidad, tiempo_valor, tiempo_unidad):
        """
        tiempo_unidad: 0=minutos, 1=horas, 2=dias
        """
        self.login()
        
        # En Omada v6 la ruta para crear grupos de fichas es voucherGroups
        url = f"{self.base_url}/{self.omadac_id}/api/v2/hotspot/sites/{self.site_id}/voucherGroups"
        
        # En Omada V6 durationType=1 parece ser Minutos
        payload = {
            "amount": cantidad,
            "applyToAllPortals": True,
            "codeForm": [0], # Numerico
            "codeLength": 6,
            "description": "Auto API",
            "duration": tiempo_valor, # Minutos
            "durationType": 1,
            "endTime": "23:59",
            "logout": True,
            "maxUsers": 1,
            "name": f"API_{tiempo_valor}m",
            "pattern": {"patternType": 0, "position": 0, "ssidNetworkEnable": False, "durationEnable": False, "limitEnable": False},
            "scheduleTime": 0,
            "startTime": "00:00",
            "trafficLimitEnable": False,
            "upTimeLimitEnable": False,
            "validityType": 0,
            "voucherValidityEnable": False,
            "weeklyEnableDays": {"1": True, "2": True, "3": True, "4": True, "5": True, "6": True, "7": True},
            "type": 0
        }
        
        res = self.session.post(url, json=payload, timeout=15)
        data = res.json()
        
        if data.get('errorCode') != 0:
            raise Exception(f"Error generando fichas: {data.get('msg')} | Payload enviado: {payload}")
            
        vouchers = []
        
        # Consultar los vouchers recién creados si no vienen en la respuesta
        try:
            # Ordenados por creationTime descendente, tomar los primeros N
            # En V6 los vouchers individuales se listan en /vouchers
            query_url = f"{self.base_url}/{self.omadac_id}/api/v2/hotspot/sites/{self.site_id}/vouchers?currentPage=1&currentPageSize={cantidad}&sort=createTime&order=desc"
            q_res = self.session.get(query_url, timeout=10)
            q_data = q_res.json()
            if q_data.get('errorCode') == 0:
                lista = q_data.get('result', {}).get('data', [])
                vouchers = [v.get('code') for v in lista]
        except:
            pass
            
        return vouchers
