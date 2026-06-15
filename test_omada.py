import requests
import urllib3
import json
from app import app, ConfigOmada

# Disable SSL warnings because Omada usually has self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_omada_connection():
    with app.app_context():
        config = ConfigOmada.query.first()
        if not config or not config.activo:
            print("Omada no está configurado o está desactivado.")
            return

        base_url = config.url.rstrip('/')
        username = config.username
        password = config.password
        
        session = requests.Session()
        session.verify = False # Ignore SSL errors
        
        try:
            print(f"1. Intentando obtener OmadacId desde {base_url}/api/info...")
            info_req = session.get(f"{base_url}/api/info", timeout=10)
            if info_req.status_code != 200:
                print(f"Error al obtener info: {info_req.status_code} {info_req.text}")
                return
                
            info_data = info_req.json()
            omadac_id = info_data.get('result', {}).get('omadacId')
            print(f"OmadacId obtenido: {omadac_id}")
            
            print(f"2. Intentando login...")
            login_url = f"{base_url}/{omadac_id}/api/v2/login"
            login_data = {
                "username": username,
                "password": password
            }
            login_req = session.post(login_url, json=login_data, timeout=10)
            
            if login_req.status_code != 200:
                print(f"Error en login (HTTP {login_req.status_code}): {login_req.text}")
                return
                
            login_resp = login_req.json()
            if login_resp.get('errorCode') != 0:
                print(f"Login fallido: {login_resp}")
                return
                
            token = login_resp.get('result', {}).get('token')
            print(f"Login exitoso! Token obtenido: {token[:10]}...")
            
            # Update session header with token
            session.headers.update({"Csrf-Token": token})
            
            print(f"3. Obteniendo lista de sitios...")
            sites_url = f"{base_url}/{omadac_id}/api/v2/sites"
            sites_req = session.get(sites_url, timeout=10)
            sites_data = sites_req.json()
            
            if sites_data.get('errorCode') == 0:
                sites = sites_data.get('result', {}).get('data', [])
                print("Sitios disponibles:")
                for s in sites:
                    print(f" - {s.get('name')}: {s.get('id')}")
            else:
                print(f"No se pudieron cargar los sitios: {sites_data}")
                
        except Exception as e:
            print(f"Excepción durante la prueba: {e}")

if __name__ == "__main__":
    test_omada_connection()
