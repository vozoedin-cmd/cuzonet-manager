
from app import app, db, ConfigMikroTik
with app.app_context():
    routers = ConfigMikroTik.query.all()
    print(f"Total routers: {len(routers)}")
    for r in routers:
        print(f"ID: {r.id}, Host: {r.host}, Port: {r.port}, User: {r.username}, Activo: {r.activo}")
