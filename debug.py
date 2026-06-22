from app import app, db, OmadaVoucher

with app.app_context():
    vouchers = OmadaVoucher.query.filter_by(estado='activo').limit(10).all()
    print("Activos:", [(v.codigo, v.estado, v.omada_id) for v in vouchers])
    
    vouchers_all = OmadaVoucher.query.limit(10).all()
    print("Todos:", [(v.codigo, v.estado, v.omada_id) for v in vouchers_all])
