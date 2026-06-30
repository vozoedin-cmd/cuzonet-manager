from app import app, db
from sqlalchemy import text

def run_migration():
    with app.app_context():
        try:
            print("Running migration for database...")
            columns = [
                "uisp_id VARCHAR(100)",
                "mac VARCHAR(50)",
                "estado_online BOOLEAN DEFAULT FALSE",
                "rssi INTEGER",
                "ccq FLOAT",
                "airmax_quality FLOAT",
                "trafico_tx FLOAT",
                "trafico_rx FLOAT",
                "temperatura FLOAT",
                "cpu FLOAT",
                "ram FLOAT",
                "voltaje FLOAT",
                "uptime VARCHAR(100)",
                "gps VARCHAR(100)",
                "firmware VARCHAR(50)",
                "clientes_conectados INTEGER DEFAULT 0",
                "ultima_sincronizacion TIMESTAMP"
            ]
            
            for col in columns:
                col_name = col.split(' ')[0]
                try:
                    db.session.execute(text(f"ALTER TABLE infraestructura ADD COLUMN {col}"))
                    db.session.commit()
                    print(f"Added column {col_name}")
                except Exception as e:
                    db.session.rollback()
                    if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                        print(f"Column {col_name} already exists, skipping.")
                    else:
                        print(f"Error adding {col_name}: {e}")
            
            print("Migration completed successfully!")
            
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == '__main__':
    run_migration()
