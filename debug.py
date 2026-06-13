import sys
import traceback
from app import app, db, Usuario, ConfigMikroTik, PlanHotspot, TransaccionVendedor, Voucher
from flask import render_template

with app.app_context():
    try:
        print("Testing hotspot_vendedores route rendering...")
        vendedores = Usuario.query.filter_by(rol='vendedor').all()
        routers = ConfigMikroTik.query.filter_by(tipo='hotspot').all()
        
        vendedores_data = []
        for v in vendedores:
            fichas_impresas = Voucher.query.filter_by(vendedor_id=v.id).count()
            abonos = TransaccionVendedor.query.filter_by(vendedor_id=v.id, tipo='abono').all()
            total_abonado = sum(a.monto for a in abonos)
            
            vendedores_data.append({
                'vendedor': v,
                'fichas_impresas': fichas_impresas,
                'total_abonado': total_abonado
            })
            
        with app.test_request_context('/admin/hotspot/vendedores'):
            render_template('hotspot_vendedores.html', 
                            vendedores_data=vendedores_data,
                            routers=routers)
        print("hotspot_vendedores.html renders FINE!")

        print("Testing hotspot_dashboard route rendering...")
        planes = PlanHotspot.query.all()
        todos_routers = ConfigMikroTik.query.all()
        transacciones = TransaccionVendedor.query.order_by(TransaccionVendedor.fecha.desc()).limit(50).all()
        total_vouchers = Voucher.query.count()
        ganancia_total = db.session.query(db.func.sum(Voucher.precio)).scalar() or 0.0

        with app.test_request_context('/admin/hotspot'):
            render_template('hotspot_dashboard.html',
                            planes=planes,
                            routers=routers,
                            todos_routers=todos_routers,
                            vendedores=vendedores,
                            transacciones=transacciones,
                            total_vouchers=total_vouchers,
                            ganancia_total=ganancia_total)
        print("hotspot_dashboard.html renders FINE!")

        print("Testing hotspot_impresion_multiple route rendering...")
        with app.test_request_context('/admin/hotspot/fichas'):
            render_template('hotspot_impresion_multiple.html', planes=planes)
        print("hotspot_impresion_multiple.html renders FINE!")

    except Exception as e:
        print("ERROR FOUND:")
        traceback.print_exc()
