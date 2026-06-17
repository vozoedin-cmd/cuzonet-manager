import requests
import urllib3
import json
from app import app, ConfigOmada

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

with app.app_context():
    config = ConfigOmada.query.first()
    if not config:
        print("No omada config")
        exit()
    base_url = config.url.rstrip('/')
    session = requests.Session()
    session.verify = False
    
    info_req = session.get(f"{base_url}/api/info", timeout=10)
    omadac_id = info_req.json().get('result', {}).get('omadacId')
    
    login_req = session.post(f"{base_url}/{omadac_id}/api/v2/login", json={"username": config.username, "password": config.password})
    token = login_req.json().get('result', {}).get('token')
    session.headers.update({"Csrf-Token": token})
    
    sites_req = session.get(f"{base_url}/{omadac_id}/api/v2/sites")
    site_id = sites_req.json().get('result', {}).get('data', [])[0].get('id')
    
    vouchers_req = session.get(f"{base_url}/{omadac_id}/api/v2/hotspot/sites/{site_id}/vouchers?currentPage=1&currentPageSize=10")
    print(json.dumps(vouchers_req.json(), indent=2))
