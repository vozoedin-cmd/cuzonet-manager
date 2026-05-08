
from app import app, db, ConfigMikroTik
with app.app_context():
    for r in ConfigMikroTik.query.all():
        print(f"Router: {r.nombre}, Host: {r.host}, UserLen: {len(r.username)}, PassLen: {len(r.password)}, Active: {r.activo}")
