import sys
import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import urllib3
urllib3.disable_warnings()

from app import app, db, ConfigMikroTik

with app.app_context():
    router = ConfigMikroTik.query.filter_by(activo=True).first()
    if not router:
        print("No active router found.")
        sys.exit(1)
        
    print(f"Testing router: {router.host}:{router.port} (SSL: {router.use_ssl})")
    protocol = 'https' if router.use_ssl else 'http'
    url = f"{protocol}://{router.host}:{router.port}/rest/system/identity"
    
    print(f"URL: {url}")
    print("1. Trying plain GET without auth...")
    try:
        r = requests.get(url, verify=False, timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Headers: {r.headers}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n2. Trying GET with Basic Auth in Session...")
    try:
        s = requests.Session()
        s.auth = (router.username, router.password)
        s.verify = False
        r = s.get(url, timeout=5)
        print(f"Status: {r.status_code}")
        print(f"Headers: {r.headers}")
        print(f"Content: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

    print("\n3. Trying GET with explicit Basic Auth...")
    try:
        r = requests.get(url, auth=HTTPBasicAuth(router.username, router.password), verify=False, timeout=5)
        print(f"Status: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")
