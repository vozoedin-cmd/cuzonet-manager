import sys
from app import app, db, Usuario

with app.app_context():
    # Revisar si hay vendedores
    vendedores = Usuario.query.filter_by(rol='vendedor').all()
    print(f"Vendedores actuales en DB: {len(vendedores)}")
    for v in vendedores:
        print(f" - {v.username} ({v.nombre})")
        
    with app.test_client() as c:
        # Simulamos que somos el admin (forzamos login)
        with c.session_transaction() as sess:
            sess['_user_id'] = '1' # Asumimos que admin es ID 1
            sess['_fresh'] = True
            
        print("\nSimulando peticion POST a /admin/hotspot/vendedor/guardar...")
        response = c.post('/admin/hotspot/vendedor/guardar', data={
            'vendedor_id': '',
            'tipo_vendedor': 'prepago',
            'nombre': 'Vendedor Prueba',
            'username': '5551234567',
            'password': 'password123',
            'router_id': ''
        }, follow_redirects=True)
        
        print("Respuesta del servidor:", response.status_code)
        
        vendedores_despues = Usuario.query.filter_by(rol='vendedor').all()
        print(f"Vendedores despues en DB: {len(vendedores_despues)}")
        for v in vendedores_despues:
            print(f" - {v.username} ({v.nombre})")
