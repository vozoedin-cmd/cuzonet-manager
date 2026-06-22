from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Intentar agregar las columnas nuevas a config_mikrotik
        db.session.execute(text('ALTER TABLE config_mikrotik ADD COLUMN estado_online BOOLEAN DEFAULT TRUE;'))
        db.session.commit()
        print("Columna 'estado_online' agregada a config_mikrotik.")
    except Exception as e:
        db.session.rollback()
        print("La columna 'estado_online' ya existe o hubo un error:", e)

    try:
        db.session.execute(text('ALTER TABLE config_mikrotik ADD COLUMN ultima_caida TIMESTAMP;'))
        db.session.commit()
        print("Columna 'ultima_caida' agregada a config_mikrotik.")
    except Exception as e:
        db.session.rollback()
        print("La columna 'ultima_caida' ya existe o hubo un error:", e)

    try:
        # Crear la tabla nueva si no existe
        db.create_all()
        print("Se verificaron y crearon las tablas faltantes (ej. config_alertas).")
    except Exception as e:
        print("Error al crear tablas:", e)

    print("\n¡Migración completada exitosamente! Ya puedes iniciar el servidor con python app.py")
