"""
MikroTik Client Manager - Aplicación Web
Registra clientes y crea Simple Queues automáticamente en MikroTik
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cuzonet-secret-key-2024')

# Configuración de base de datos
# Para desarrollo usa SQLite, para producción usa PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///clientes.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============== MODELOS ==============

class Cliente(db.Model):
    """Modelo de Cliente"""
    __tablename__ = 'clientes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(15), nullable=False, unique=True)
    plan = db.Column(db.String(50), nullable=False)
    velocidad_download = db.Column(db.String(20), nullable=False)  # ej: "10M"
    velocidad_upload = db.Column(db.String(20), nullable=False)    # ej: "5M"
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    estado = db.Column(db.String(20), default='activo')  # activo, suspendido
    queue_name = db.Column(db.String(100))  # Nombre del queue en MikroTik
    mikrotik_id = db.Column(db.String(50))  # ID del queue en MikroTik
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'ip_address': self.ip_address,
            'plan': self.plan,
            'velocidad_download': self.velocidad_download,
            'velocidad_upload': self.velocidad_upload,
            'telefono': self.telefono,
            'direccion': self.direccion,
            'estado': self.estado,
            'queue_name': self.queue_name,
            'mikrotik_id': self.mikrotik_id,
            'fecha_registro': self.fecha_registro.strftime('%Y-%m-%d %H:%M') if self.fecha_registro else None
        }


class ConfigMikroTik(db.Model):
    """Configuración de conexión a MikroTik"""
    __tablename__ = 'config_mikrotik'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), default='Principal')
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, default=8728)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    use_ssl = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)


class Plan(db.Model):
    """Planes de internet predefinidos"""
    __tablename__ = 'planes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)
    velocidad_download = db.Column(db.String(20), nullable=False)
    velocidad_upload = db.Column(db.String(20), nullable=False)
    precio = db.Column(db.Float, default=0)
    descripcion = db.Column(db.String(200))


# ============== API MIKROTIK ==============

class MikroTikAPI:
    """Clase para interactuar con MikroTik REST API"""
    
    def __init__(self, host, username, password, port=80, use_ssl=False):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.protocol = 'https' if use_ssl else 'http'
        self.base_url = f"{self.protocol}://{self.host}:{self.port}/rest"
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = False  # Para certificados auto-firmados
    
    def test_connection(self):
        """Prueba la conexión al router"""
        try:
            response = self.session.get(f"{self.base_url}/system/identity", timeout=10)
            if response.status_code == 200:
                return True, response.json().get('name', 'MikroTik')
            return False, f"Error: {response.status_code}"
        except Exception as e:
            return False, str(e)
    
    def create_simple_queue(self, name, target, max_limit_download, max_limit_upload, comment=""):
        """
        Crea un Simple Queue en MikroTik
        
        Args:
            name: Nombre del queue (ej: "cliente-juan")
            target: IP del cliente (ej: "192.168.1.100/32")
            max_limit_download: Velocidad de bajada (ej: "10M")
            max_limit_upload: Velocidad de subida (ej: "5M")
            comment: Comentario opcional
        
        Returns:
            tuple: (success, queue_id or error_message)
        """
        try:
            # Formato de max-limit: "upload/download"
            max_limit = f"{max_limit_upload}/{max_limit_download}"
            
            data = {
                "name": name,
                "target": target if '/32' in target else f"{target}/32",
                "max-limit": max_limit,
                "comment": comment
            }
            
            response = self.session.put(
                f"{self.base_url}/queue/simple",
                json=data,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                queue_id = result.get('.id', '')
                return True, queue_id
            else:
                return False, f"Error {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def update_simple_queue(self, queue_id, **kwargs):
        """Actualiza un Simple Queue existente"""
        try:
            data = {}
            if 'name' in kwargs:
                data['name'] = kwargs['name']
            if 'target' in kwargs:
                target = kwargs['target']
                data['target'] = target if '/32' in target else f"{target}/32"
            if 'max_limit_download' in kwargs and 'max_limit_upload' in kwargs:
                data['max-limit'] = f"{kwargs['max_limit_upload']}/{kwargs['max_limit_download']}"
            if 'disabled' in kwargs:
                data['disabled'] = 'yes' if kwargs['disabled'] else 'no'
            if 'comment' in kwargs:
                data['comment'] = kwargs['comment']
            
            response = self.session.patch(
                f"{self.base_url}/queue/simple/{queue_id}",
                json=data,
                timeout=15
            )
            
            return response.status_code == 200, response.text
            
        except Exception as e:
            return False, str(e)
    
    def delete_simple_queue(self, queue_id):
        """Elimina un Simple Queue"""
        try:
            response = self.session.delete(
                f"{self.base_url}/queue/simple/{queue_id}",
                timeout=15
            )
            return response.status_code in [200, 204], response.text
        except Exception as e:
            return False, str(e)
    
    def get_simple_queues(self):
        """Obtiene todos los Simple Queues"""
        try:
            response = self.session.get(
                f"{self.base_url}/queue/simple",
                timeout=15
            )
            if response.status_code == 200:
                return True, response.json()
            return False, f"Error {response.status_code}"
        except Exception as e:
            return False, str(e)
    
    def suspend_queue(self, queue_id):
        """Suspende (deshabilita) un queue"""
        return self.update_simple_queue(queue_id, disabled=True)
    
    def activate_queue(self, queue_id):
        """Activa (habilita) un queue"""
        return self.update_simple_queue(queue_id, disabled=False)


def get_mikrotik_api():
    """Obtiene instancia de la API de MikroTik con la configuración activa"""
    config = ConfigMikroTik.query.filter_by(activo=True).first()
    if not config:
        return None
    return MikroTikAPI(
        host=config.host,
        username=config.username,
        password=config.password,
        port=config.port,
        use_ssl=config.use_ssl
    )


# ============== RUTAS WEB ==============

@app.route('/')
def index():
    """Página principal - Dashboard"""
    clientes = Cliente.query.order_by(Cliente.fecha_registro.desc()).all()
    total_clientes = Cliente.query.count()
    clientes_activos = Cliente.query.filter_by(estado='activo').count()
    clientes_suspendidos = Cliente.query.filter_by(estado='suspendido').count()
    planes = Plan.query.all()
    
    return render_template('index.html', 
                         clientes=clientes,
                         total_clientes=total_clientes,
                         clientes_activos=clientes_activos,
                         clientes_suspendidos=clientes_suspendidos,
                         planes=planes)


@app.route('/clientes')
def listar_clientes():
    """Lista todos los clientes"""
    clientes = Cliente.query.order_by(Cliente.fecha_registro.desc()).all()
    planes = Plan.query.all()
    return render_template('clientes.html', clientes=clientes, planes=planes)


@app.route('/configuracion')
def configuracion():
    """Página de configuración de MikroTik"""
    config = ConfigMikroTik.query.first()
    planes = Plan.query.all()
    return render_template('configuracion.html', config=config, planes=planes)


# ============== API ENDPOINTS ==============

@app.route('/api/cliente', methods=['POST'])
def crear_cliente():
    """Crear nuevo cliente y Simple Queue en MikroTik"""
    try:
        data = request.get_json()
        
        # Validaciones
        if not data.get('nombre'):
            return jsonify({'success': False, 'error': 'El nombre es requerido'}), 400
        if not data.get('ip_address'):
            return jsonify({'success': False, 'error': 'La IP es requerida'}), 400
        
        # Verificar IP duplicada
        existing = Cliente.query.filter_by(ip_address=data['ip_address']).first()
        if existing:
            return jsonify({'success': False, 'error': 'Esta IP ya está registrada'}), 400
        
        # Obtener velocidades del plan o usar las proporcionadas
        vel_download = data.get('velocidad_download', '10M')
        vel_upload = data.get('velocidad_upload', '5M')
        
        if data.get('plan_id'):
            plan = Plan.query.get(data['plan_id'])
            if plan:
                vel_download = plan.velocidad_download
                vel_upload = plan.velocidad_upload
        
        # Generar nombre del queue
        nombre_limpio = data['nombre'].replace(' ', '-').lower()[:30]
        queue_name = f"cliente-{nombre_limpio}-{data['ip_address'].replace('.', '-')}"
        
        # Crear Simple Queue en MikroTik
        mikrotik_id = None
        api = get_mikrotik_api()
        
        if api:
            success, result = api.create_simple_queue(
                name=queue_name,
                target=data['ip_address'],
                max_limit_download=vel_download,
                max_limit_upload=vel_upload,
                comment=f"Cliente: {data['nombre']}"
            )
            
            if success:
                mikrotik_id = result
            else:
                return jsonify({
                    'success': False, 
                    'error': f'Error al crear queue en MikroTik: {result}'
                }), 500
        
        # Crear cliente en base de datos
        cliente = Cliente(
            nombre=data['nombre'],
            ip_address=data['ip_address'],
            plan=data.get('plan', 'Básico'),
            velocidad_download=vel_download,
            velocidad_upload=vel_upload,
            telefono=data.get('telefono', ''),
            direccion=data.get('direccion', ''),
            queue_name=queue_name,
            mikrotik_id=mikrotik_id,
            estado='activo'
        )
        
        db.session.add(cliente)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Cliente registrado exitosamente',
            'cliente': cliente.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cliente/<int:id>', methods=['PUT'])
def actualizar_cliente(id):
    """Actualizar cliente existente"""
    try:
        cliente = Cliente.query.get_or_404(id)
        data = request.get_json()
        
        # Actualizar campos
        if data.get('nombre'):
            cliente.nombre = data['nombre']
        if data.get('telefono'):
            cliente.telefono = data['telefono']
        if data.get('direccion'):
            cliente.direccion = data['direccion']
        
        # Si cambia la velocidad, actualizar en MikroTik
        if data.get('velocidad_download') or data.get('velocidad_upload'):
            cliente.velocidad_download = data.get('velocidad_download', cliente.velocidad_download)
            cliente.velocidad_upload = data.get('velocidad_upload', cliente.velocidad_upload)
            
            if cliente.mikrotik_id:
                api = get_mikrotik_api()
                if api:
                    api.update_simple_queue(
                        cliente.mikrotik_id,
                        max_limit_download=cliente.velocidad_download,
                        max_limit_upload=cliente.velocidad_upload
                    )
        
        db.session.commit()
        return jsonify({'success': True, 'cliente': cliente.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cliente/<int:id>', methods=['DELETE'])
def eliminar_cliente(id):
    """Eliminar cliente y su queue de MikroTik"""
    try:
        cliente = Cliente.query.get_or_404(id)
        
        # Eliminar queue de MikroTik
        if cliente.mikrotik_id:
            api = get_mikrotik_api()
            if api:
                api.delete_simple_queue(cliente.mikrotik_id)
        
        db.session.delete(cliente)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Cliente eliminado'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cliente/<int:id>/suspender', methods=['POST'])
def suspender_cliente(id):
    """Suspender cliente (deshabilitar queue)"""
    try:
        cliente = Cliente.query.get_or_404(id)
        
        if cliente.mikrotik_id:
            api = get_mikrotik_api()
            if api:
                success, msg = api.suspend_queue(cliente.mikrotik_id)
                if not success:
                    return jsonify({'success': False, 'error': f'Error MikroTik: {msg}'}), 500
        
        cliente.estado = 'suspendido'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Cliente suspendido'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cliente/<int:id>/activar', methods=['POST'])
def activar_cliente(id):
    """Activar cliente (habilitar queue)"""
    try:
        cliente = Cliente.query.get_or_404(id)
        
        if cliente.mikrotik_id:
            api = get_mikrotik_api()
            if api:
                success, msg = api.activate_queue(cliente.mikrotik_id)
                if not success:
                    return jsonify({'success': False, 'error': f'Error MikroTik: {msg}'}), 500
        
        cliente.estado = 'activo'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Cliente activado'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/clientes', methods=['GET'])
def obtener_clientes():
    """Obtener lista de clientes"""
    clientes = Cliente.query.order_by(Cliente.fecha_registro.desc()).all()
    return jsonify({
        'success': True,
        'clientes': [c.to_dict() for c in clientes]
    })


# ============== CONFIGURACIÓN ==============

@app.route('/api/config/mikrotik', methods=['POST'])
def guardar_config_mikrotik():
    """Guardar configuración de MikroTik"""
    try:
        data = request.get_json()
        
        config = ConfigMikroTik.query.first()
        if not config:
            config = ConfigMikroTik()
        
        config.host = data.get('host', '')
        config.port = int(data.get('port', 80))
        config.username = data.get('username', '')
        config.password = data.get('password', '')
        config.use_ssl = data.get('use_ssl', False)
        config.activo = True
        
        db.session.add(config)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuración guardada'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config/mikrotik/test', methods=['POST'])
def probar_conexion_mikrotik():
    """Probar conexión a MikroTik"""
    try:
        data = request.get_json()
        
        api = MikroTikAPI(
            host=data.get('host', ''),
            username=data.get('username', ''),
            password=data.get('password', ''),
            port=int(data.get('port', 80)),
            use_ssl=data.get('use_ssl', False)
        )
        
        success, result = api.test_connection()
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Conexión exitosa a: {result}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Error de conexión: {result}'
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/planes', methods=['GET'])
def obtener_planes():
    """Obtener lista de planes"""
    planes = Plan.query.all()
    return jsonify({
        'success': True,
        'planes': [{
            'id': p.id,
            'nombre': p.nombre,
            'velocidad_download': p.velocidad_download,
            'velocidad_upload': p.velocidad_upload,
            'precio': p.precio
        } for p in planes]
    })


@app.route('/api/plan', methods=['POST'])
def crear_plan():
    """Crear nuevo plan"""
    try:
        data = request.get_json()
        
        plan = Plan(
            nombre=data.get('nombre', ''),
            velocidad_download=data.get('velocidad_download', '10M'),
            velocidad_upload=data.get('velocidad_upload', '5M'),
            precio=float(data.get('precio', 0)),
            descripcion=data.get('descripcion', '')
        )
        
        db.session.add(plan)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Plan creado'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plan/<int:id>', methods=['DELETE'])
def eliminar_plan(id):
    """Eliminar plan"""
    try:
        plan = Plan.query.get_or_404(id)
        db.session.delete(plan)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Plan eliminado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== SINCRONIZACIÓN MIKROTIK ==============

@app.route('/api/sync/queues', methods=['GET'])
def sincronizar_queues():
    """Obtener queues de MikroTik para sincronización"""
    try:
        api = get_mikrotik_api()
        if not api:
            return jsonify({'success': False, 'error': 'MikroTik no configurado'}), 400
        
        success, queues = api.get_simple_queues()
        
        if success:
            return jsonify({'success': True, 'queues': queues})
        else:
            return jsonify({'success': False, 'error': queues}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== INICIALIZAR DB ==============

def init_db():
    """Inicializar base de datos y crear tablas"""
    with app.app_context():
        db.create_all()
        
        # Crear planes por defecto si no existen
        if Plan.query.count() == 0:
            planes_default = [
                Plan(nombre='Básico 5Mbps', velocidad_download='5M', velocidad_upload='2M', precio=15.00),
                Plan(nombre='Estándar 10Mbps', velocidad_download='10M', velocidad_upload='5M', precio=25.00),
                Plan(nombre='Premium 20Mbps', velocidad_download='20M', velocidad_upload='10M', precio=35.00),
                Plan(nombre='Ultra 50Mbps', velocidad_download='50M', velocidad_upload='25M', precio=50.00),
                Plan(nombre='Empresarial 100Mbps', velocidad_download='100M', velocidad_upload='50M', precio=100.00),
            ]
            for plan in planes_default:
                db.session.add(plan)
            db.session.commit()
            print("[OK] Planes por defecto creados")
        
        print("[OK] Base de datos inicializada")


if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
