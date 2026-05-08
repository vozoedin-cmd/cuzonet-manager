import sys
import requests
import urllib3
urllib3.disable_warnings()

from app import app, ConfigMikroTik

with app.app_context():
    routers = ConfigMikroTik.query.filter_by(activo=True).all()
    print(f"Found {len(routers)} active routers.")
    
    for router in routers:
        print(f"\n--- Testing router: {router.nombre} ({router.host}:{router.port}) ---")
        protocol = 'https' if router.use_ssl else 'http'
        url = f"{protocol}://{router.host}:{router.port}/rest/system/identity"
        
        s = requests.Session()
        s.auth = (router.username, router.password)
        s.verify = False
        try:
            r = s.get(url, timeout=5)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                print(f"Content: {r.text[:100]}")
            else:
                print(f"Error Content: {r.text[:100]}")
        except Exception as e:
            print(f"Exception: {e}")
