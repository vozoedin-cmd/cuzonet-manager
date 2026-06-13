from app import app, db, Usuario
import traceback

with app.app_context():
    try:
        print("Intentando crear vendedor de prueba directo en base de datos...")
        vendedor = Usuario(
            username='vendedor_test_999',
            nombre='Test Vendedor',
            rol='vendedor',
            router_id=None,
            activo=True,
            balance=0.0
        )
        vendedor.set_password('test1234')
        db.session.add(vendedor)
        db.session.commit()
        print("EXITO: Se guardo el vendedor sin problemas de DB.")
        
        # Lo eliminamos para no ensuciar
        db.session.delete(vendedor)
        db.session.commit()
        
    except Exception as e:
        print("FALLO:")
        traceback.print_exc()
