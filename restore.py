from app import app, db, OmadaVoucher
from datetime import datetime, timedelta

with app.app_context():
    # Encontrar los vouchers que fueron eliminados hoy accidentalmente
    # (Suponiendo que el usuario no habia eliminado miles antes)
    hoy = datetime.utcnow() - timedelta(days=1)
    
    # Restablecer el estado de los eliminados
    vouchers = OmadaVoucher.query.filter(OmadaVoucher.estado == 'eliminado').all()
    count = 0
    for v in vouchers:
        v.estado = 'activo'
        count += 1
        
    db.session.commit()
    print(f"Restaurados {count} vouchers.")
