import json
from omada_api import OmadaAPI
from app import app, ConfigOmada

with app.app_context():
    config = ConfigOmada.query.filter_by(activo=True).first()
    if not config:
        print("No active Omada config")
        exit()

    omada = OmadaAPI(config.url, config.username, config.password, config.site_id)
    sites = omada.get_all_sites()
    print("Sites:", sites)
    
    if not sites:
        print("No sites found")
        exit()
        
    omada.site_id = sites[0]['id']
    query_url = f"{omada.base_url}/{omada.omadac_id}/api/v2/hotspot/sites/{omada.site_id}/vouchers?currentPage=1&currentPageSize=5"
    res = omada.session.get(query_url, timeout=10)
    data = res.json()
    
    lista = data.get('result', {}).get('data', [])
    for v in lista:
        print(json.dumps(v, indent=2))
