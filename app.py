"""
CuzoNet Manager - Sistema de Gestión de Clientes ISP
Con funciones avanzadas: Pagos, Corte por Address List, Importar/Exportar Excel
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from io import BytesIO
import os
import json
import zipfile
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cuzonet-secret-key-2024')

# Configuración de base de datos
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///clientes.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============== LOGIN MANAGER ==============
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Inicia sesión para acceder al sistema'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ============== MODELOS ==============

class Usuario(UserMixin, db.Model):
    """Modelo de usuarios del sistema"""
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre = db.Column(db.String(100), default='Administrador')
    rol = db.Column(db.String(20), default='admin')  # admin, operador
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Cliente(db.Model):
    """Modelo de Cliente con campos adicionales para pagos y corte"""
    __tablename__ = 'clientes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(15), nullable=False, unique=True)
    plan = db.Column(db.String(50), nullable=False)
    velocidad_download = db.Column(db.String(20), nullable=False)
    velocidad_upload = db.Column(db.String(20), nullable=False)
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))
    direccion = db.Column(db.String(200))
    cedula = db.Column(db.String(20))
    
    # Estado y MikroTik
    estado = db.Column(db.String(20), default='activo')  # activo, suspendido, cortado
    queue_name = db.Column(db.String(100))
    mikrotik_id = db.Column(db.String(50))
    
    # Fechas de pago
    dia_corte = db.Column(db.Integer, default=1)  # Día del mes para corte (1-31)
    fecha_ultimo_pago = db.Column(db.DateTime)
    fecha_proximo_pago = db.Column(db.DateTime)
    precio_mensual = db.Column(db.Float, default=0)
    saldo_pendiente = db.Column(db.Float, default=0)
    
    # Ubicación geográfica
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    
    # Fechas de registro
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con pagos
    pagos = db.relationship('Pago', backref='cliente', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'ip_address': self.ip_address,
            'plan': self.plan,
            'velocidad_download': self.velocidad_download,
            'velocidad_upload': self.velocidad_upload,
            'telefono': self.telefono,
            'email': self.email,
            'direccion': self.direccion,
            'cedula': self.cedula,
            'estado': self.estado,
            'queue_name': self.queue_name,
            'mikrotik_id': self.mikrotik_id,
            'dia_corte': self.dia_corte,
            'fecha_ultimo_pago': self.fecha_ultimo_pago.strftime('%Y-%m-%d') if self.fecha_ultimo_pago else None,
            'fecha_proximo_pago': self.fecha_proximo_pago.strftime('%Y-%m-%d') if self.fecha_proximo_pago else None,
            'precio_mensual': self.precio_mensual,
            'saldo_pendiente': self.saldo_pendiente,
            'latitud': self.latitud,
            'longitud': self.longitud,
            'fecha_registro': self.fecha_registro.strftime('%Y-%m-%d %H:%M') if self.fecha_registro else None
        }


class Pago(db.Model):
    """Modelo de Pagos"""
    __tablename__ = 'pagos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    mes_correspondiente = db.Column(db.String(20))  # "2024-01", "2024-02", etc.
    metodo_pago = db.Column(db.String(50))  # efectivo, transferencia, etc.
    referencia = db.Column(db.String(100))  # Número de referencia/comprobante
    notas = db.Column(db.String(200))
    registrado_por = db.Column(db.String(50))
    
    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'cliente_nombre': self.cliente.nombre if self.cliente else None,
            'monto': self.monto,
            'fecha_pago': self.fecha_pago.strftime('%Y-%m-%d %H:%M') if self.fecha_pago else None,
            'mes_correspondiente': self.mes_correspondiente,
            'metodo_pago': self.metodo_pago,
            'referencia': self.referencia,
            'notas': self.notas
        }


class ConfigMikroTik(db.Model):
    """Configuración de conexión a MikroTik"""
    __tablename__ = 'config_mikrotik'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), default='Principal')
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, default=80)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    use_ssl = db.Column(db.Boolean, default=False)
    activo = db.Column(db.Boolean, default=True)
    # Nombre del address list para clientes cortados
    address_list_cortados = db.Column(db.String(50), default='MOROSOS')


class Plan(db.Model):
    """Planes de internet predefinidos"""
    __tablename__ = 'planes'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)
    velocidad_download = db.Column(db.String(20), nullable=False)
    velocidad_upload = db.Column(db.String(20), nullable=False)
    precio = db.Column(db.Float, default=0)
    descripcion = db.Column(db.String(200))


class AuditLog(db.Model):
    """Registro de actividad del sistema"""
    __tablename__ = 'audit_log'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), nullable=False)
    accion = db.Column(db.String(50), nullable=False)  # crear, editar, eliminar, pago, corte, activar, login, etc.
    entidad = db.Column(db.String(50))  # cliente, pago, config, etc.
    entidad_id = db.Column(db.Integer)
    detalle = db.Column(db.String(500))
    ip_origen = db.Column(db.String(45))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'usuario': self.usuario,
            'accion': self.accion,
            'entidad': self.entidad,
            'entidad_id': self.entidad_id,
            'detalle': self.detalle,
            'ip_origen': self.ip_origen,
            'fecha': self.fecha.strftime('%Y-%m-%d %H:%M:%S') if self.fecha else None
        }


def registrar_auditoria(accion, entidad=None, entidad_id=None, detalle=None):
    """Helper para registrar eventos de auditoría"""
    try:
        usuario = current_user.username if current_user.is_authenticated else 'sistema'
        ip = request.remote_addr if request else None
        log = AuditLog(
            usuario=usuario,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
            ip_origen=ip
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"[AUDIT] Error: {e}")


# ============== API MIKROTIK ==============

# Caché del estado de MikroTik para evitar consultas repetidas
_mikrotik_status_cache = {
    'connected': False,
    'message': 'Sin verificar',
    'queue_count': 0,
    'last_check': None
}
MIKROTIK_CACHE_TTL = 60  # Segundos antes de volver a consultar al router

def limpiar_texto_mikrotik(texto):
    """Limpia acentos y caracteres especiales para MikroTik"""
    if not texto:
        return texto
    # Mapa de reemplazo de caracteres
    reemplazos = {
        'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ã': 'a',
        'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u',
        'ñ': 'n', 'ç': 'c',
        'Á': 'A', 'À': 'A', 'Ä': 'A', 'Â': 'A', 'Ã': 'A',
        'É': 'E', 'È': 'E', 'Ë': 'E', 'Ê': 'E',
        'Í': 'I', 'Ì': 'I', 'Ï': 'I', 'Î': 'I',
        'Ó': 'O', 'Ò': 'O', 'Ö': 'O', 'Ô': 'O', 'Õ': 'O',
        'Ú': 'U', 'Ù': 'U', 'Ü': 'U', 'Û': 'U',
        'Ñ': 'N', 'Ç': 'C'
    }
    resultado = str(texto)
    for original, reemplazo in reemplazos.items():
        resultado = resultado.replace(original, reemplazo)
    return resultado

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
        self.session.verify = False
    
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
        """Crea un Simple Queue en MikroTik"""
        try:
            max_limit = f"{max_limit_upload}/{max_limit_download}"
            
            # Limpiar acentos para MikroTik
            nombre_limpio = limpiar_texto_mikrotik(name)
            comentario_limpio = limpiar_texto_mikrotik(comment)
            
            data = {
                "name": nombre_limpio,
                "target": target if '/32' in target else f"{target}/32",
                "max-limit": max_limit,
                "comment": comentario_limpio
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
    
    # ============== ADDRESS LIST METHODS ==============
    
    def add_to_address_list(self, ip_address, list_name="MOROSOS", comment=""):
        """Agrega una IP al address list (para corte por firewall)"""
        try:
            data = {
                "list": list_name,
                "address": ip_address,
                "comment": comment
            }
            
            response = self.session.put(
                f"{self.base_url}/ip/firewall/address-list",
                json=data,
                timeout=15
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                return True, result.get('.id', '')
            else:
                return False, f"Error {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, str(e)
    
    def remove_from_address_list(self, ip_address, list_name="MOROSOS"):
        """Remueve una IP del address list"""
        try:
            # Primero buscar el ID de la entrada
            response = self.session.get(
                f"{self.base_url}/ip/firewall/address-list",
                params={"list": list_name, "address": ip_address},
                timeout=15
            )
            
            if response.status_code == 200:
                entries = response.json()
                for entry in entries:
                    if entry.get('address') == ip_address and entry.get('list') == list_name:
                        entry_id = entry.get('.id')
                        # Eliminar la entrada
                        del_response = self.session.delete(
                            f"{self.base_url}/ip/firewall/address-list/{entry_id}",
                            timeout=15
                        )
                        return del_response.status_code in [200, 204], "OK"
            
            return True, "No encontrado (ya eliminado)"
            
        except Exception as e:
            return False, str(e)
    
    def get_address_list(self, list_name="MOROSOS"):
        """Obtiene todas las IPs en un address list"""
        try:
            response = self.session.get(
                f"{self.base_url}/ip/firewall/address-list",
                params={"list": list_name},
                timeout=15
            )
            if response.status_code == 200:
                return True, response.json()
            return False, f"Error {response.status_code}"
        except Exception as e:
            return False, str(e)


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


def get_address_list_name():
    """Obtiene el nombre del address list configurado"""
    config = ConfigMikroTik.query.filter_by(activo=True).first()
    return config.address_list_cortados if config else "MOROSOS"


# ============== RUTAS WEB ==============

# ============== RUTAS DE AUTENTICACIÓN ==============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.activo:
            login_user(user, remember=True)
            registrar_auditoria('login', 'usuario', user.id, f'Inicio de sesión: {username}')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/cambiar-password', methods=['POST'])
@login_required
def cambiar_password():
    data = request.get_json()
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')
    
    if not current_user.check_password(current_pw):
        return jsonify({'success': False, 'error': 'Contraseña actual incorrecta'})
    if len(new_pw) < 4:
        return jsonify({'success': False, 'error': 'La nueva contraseña debe tener al menos 4 caracteres'})
    
    current_user.set_password(new_pw)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Contraseña actualizada'})

# ============== VISTAS PRINCIPALES ==============

@app.route('/')
@login_required
def index():
    """Página principal - Dashboard"""
    clientes = Cliente.query.order_by(Cliente.fecha_registro.desc()).limit(10).all()
    total_clientes = Cliente.query.count()
    clientes_activos = Cliente.query.filter_by(estado='activo').count()
    clientes_suspendidos = Cliente.query.filter(Cliente.estado.in_(['suspendido', 'cortado'])).count()
    planes = Plan.query.all()
    
    # Estadísticas de pagos del mes actual
    hoy = datetime.now()
    primer_dia_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    pagos_mes = Pago.query.filter(Pago.fecha_pago >= primer_dia_mes).all()
    total_recaudado_mes = sum(p.monto for p in pagos_mes)
    
    # Clientes próximos a corte (próximos 5 días)
    fecha_limite = hoy + timedelta(days=5)
    clientes_por_cortar = Cliente.query.filter(
        Cliente.estado == 'activo',
        Cliente.fecha_proximo_pago <= fecha_limite,
        Cliente.fecha_proximo_pago >= hoy
    ).count()
    
    return render_template('index.html', 
                         clientes=clientes,
                         total_clientes=total_clientes,
                         clientes_activos=clientes_activos,
                         clientes_suspendidos=clientes_suspendidos,
                         planes=planes,
                         total_recaudado_mes=total_recaudado_mes,
                         clientes_por_cortar=clientes_por_cortar)


@app.route('/clientes')
@login_required
def listar_clientes():
    """Lista todos los clientes"""
    clientes = Cliente.query.order_by(Cliente.fecha_registro.desc()).all()
    planes = Plan.query.all()
    return render_template('clientes.html', clientes=clientes, planes=planes)


@app.route('/pagos')
@login_required
def pagos_view():
    """Página de gestión de pagos"""
    pagos = Pago.query.order_by(Pago.fecha_pago.desc()).limit(50).all()
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return render_template('pagos.html', pagos=pagos, clientes=clientes)


@app.route('/reportes')
@login_required
def reportes_view():
    """Página de reportes y estadísticas"""
    return render_template('reportes.html')


@app.route('/api/recibo/<int:pago_id>')
def ver_recibo(pago_id):
    """Ver recibo individual de un pago"""
    pago = Pago.query.get_or_404(pago_id)
    cliente = pago.cliente
    return render_template('recibo.html', pago=pago, cliente=cliente)


@app.route('/recibos/mes')
@app.route('/recibos/mes/<mes>')
def recibos_mes(mes=None):
    """Generar recibos múltiples de un mes específico"""
    from datetime import datetime
    
    # Función para convertir número a letras en español
    def numero_a_letras(numero):
        unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
        decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 
                   'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
        especiales = {
            11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE', 15: 'QUINCE',
            16: 'DIECISEIS', 17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
            21: 'VEINTIUNO', 22: 'VEINTIDOS', 23: 'VEINTITRES', 24: 'VEINTICUATRO',
            25: 'VEINTICINCO', 26: 'VEINTISEIS', 27: 'VEINTISIETE', 28: 'VEINTIOCHO', 29: 'VEINTINUEVE'
        }
        centenas = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 
                    'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']
        
        num = int(numero)
        decimal = int(round((numero - num) * 100))
        
        if num == 0:
            letras = 'CERO'
        elif num == 100:
            letras = 'CIEN'
        elif num < 10:
            letras = unidades[num]
        elif num < 30:
            letras = especiales.get(num, decenas[num // 10])
        elif num < 100:
            if num % 10 == 0:
                letras = decenas[num // 10]
            else:
                letras = f"{decenas[num // 10]} Y {unidades[num % 10]}"
        elif num < 1000:
            if num % 100 == 0:
                letras = centenas[num // 100]
            else:
                resto = num % 100
                if resto < 30 and resto in especiales:
                    letras = f"{centenas[num // 100]} {especiales[resto]}"
                elif resto < 10:
                    letras = f"{centenas[num // 100]} {unidades[resto]}"
                elif resto % 10 == 0:
                    letras = f"{centenas[num // 100]} {decenas[resto // 10]}"
                else:
                    letras = f"{centenas[num // 100]} {decenas[resto // 10]} Y {unidades[resto % 10]}"
        else:
            miles = num // 1000
            resto = num % 1000
            if miles == 1:
                letras = 'MIL'
            else:
                letras = f"{unidades[miles]} MIL"
            if resto > 0:
                letras += ' ' + numero_a_letras(resto).replace(' QUETZALES EXACTOS', '').replace(' QUETZALES CON', '')
            letras = letras.strip()
        
        # Agregar la palabra QUETZALES
        if decimal == 0:
            return f"{letras} QUETZALES EXACTOS"
        else:
            return f"{letras} QUETZALES CON {decimal}/100"
    
    # Si no se especifica mes, usar el mes actual
    if not mes:
        mes = datetime.now().strftime('%Y-%m')
    
    # Obtener pagos del mes
    pagos = Pago.query.filter(Pago.mes_correspondiente == mes).order_by(Pago.fecha_pago.desc()).all()
    
    # Calcular total
    total = sum(p.monto for p in pagos)
    
    # Nombres de meses en español
    meses_nombres = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    
    try:
        anio, mes_num = mes.split('-')
        mes_nombre = meses_nombres.get(mes_num, mes_num)
    except:
        anio = mes[:4]
        mes_nombre = mes
    
    return render_template('recibos_multiple.html', 
                         pagos=pagos, 
                         total=total, 
                         mes=mes,
                         mes_nombre=mes_nombre,
                         anio=anio,
                         numero_a_letras=numero_a_letras)


@app.route('/avisos-cobro')
@app.route('/avisos-cobro/<mes>')
def avisos_cobro(mes=None):
    """Generar avisos de cobro (recibos antes de pagar) para todos los clientes activos"""
    from datetime import datetime
    
    # Función para convertir número a letras en español
    def numero_a_letras(numero):
        unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
        decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 
                   'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
        especiales = {
            11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE', 15: 'QUINCE',
            16: 'DIECISEIS', 17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
            21: 'VEINTIUNO', 22: 'VEINTIDOS', 23: 'VEINTITRES', 24: 'VEINTICUATRO',
            25: 'VEINTICINCO', 26: 'VEINTISEIS', 27: 'VEINTISIETE', 28: 'VEINTIOCHO', 29: 'VEINTINUEVE'
        }
        centenas = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 
                    'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']
        
        num = int(numero)
        decimal = int(round((numero - num) * 100))
        
        if num == 0:
            letras = 'CERO'
        elif num == 100:
            letras = 'CIEN'
        elif num < 10:
            letras = unidades[num]
        elif num < 30:
            letras = especiales.get(num, decenas[num // 10])
        elif num < 100:
            if num % 10 == 0:
                letras = decenas[num // 10]
            else:
                letras = f"{decenas[num // 10]} Y {unidades[num % 10]}"
        elif num < 1000:
            if num % 100 == 0:
                letras = centenas[num // 100]
            else:
                resto = num % 100
                if resto < 30 and resto in especiales:
                    letras = f"{centenas[num // 100]} {especiales[resto]}"
                elif resto < 10:
                    letras = f"{centenas[num // 100]} {unidades[resto]}"
                elif resto % 10 == 0:
                    letras = f"{centenas[num // 100]} {decenas[resto // 10]}"
                else:
                    letras = f"{centenas[num // 100]} {decenas[resto // 10]} Y {unidades[resto % 10]}"
        else:
            miles = num // 1000
            resto = num % 1000
            if miles == 1:
                letras = 'MIL'
            else:
                letras = f"{unidades[miles]} MIL"
            if resto > 0:
                letras += ' ' + numero_a_letras(resto).replace(' QUETZALES EXACTOS', '').replace(' QUETZALES CON', '')
            letras = letras.strip()
        
        if decimal == 0:
            return f"{letras} QUETZALES EXACTOS"
        else:
            return f"{letras} QUETZALES CON {decimal}/100"
    
    # Si no se especifica mes, usar el mes actual
    if not mes:
        mes = datetime.now().strftime('%Y-%m')
    
    # Obtener clientes activos
    clientes = Cliente.query.filter_by(estado='activo').order_by(Cliente.nombre).all()
    
    # Calcular total
    total = sum(c.precio_mensual for c in clientes if c.precio_mensual)
    
    # Nombres de meses en español
    meses_nombres = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    
    try:
        anio, mes_num = mes.split('-')
        mes_nombre = meses_nombres.get(mes_num, mes_num)
    except:
        anio = mes[:4]
        mes_nombre = mes
    
    return render_template('avisos_cobro.html', 
                         clientes=clientes, 
                         total=total, 
                         mes=mes,
                         mes_nombre=mes_nombre,
                         anio=anio,
                         fecha_emision=datetime.now().strftime('%d-%m-%Y'),
                         numero_a_letras=numero_a_letras)


@app.route('/aviso-cobro/cliente/<int:cliente_id>')
@app.route('/aviso-cobro/cliente/<int:cliente_id>/<mes>')
def aviso_cobro_individual(cliente_id, mes=None):
    """Generar aviso de cobro individual para un cliente"""
    from datetime import datetime
    
    def numero_a_letras(numero):
        unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
        decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 
                   'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
        especiales = {
            11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE', 15: 'QUINCE',
            16: 'DIECISEIS', 17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
            21: 'VEINTIUNO', 22: 'VEINTIDOS', 23: 'VEINTITRES', 24: 'VEINTICUATRO',
            25: 'VEINTICINCO', 26: 'VEINTISEIS', 27: 'VEINTISIETE', 28: 'VEINTIOCHO', 29: 'VEINTINUEVE'
        }
        centenas = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 
                    'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']
        
        num = int(numero)
        decimal = int(round((numero - num) * 100))
        
        if num == 0:
            letras = 'CERO'
        elif num == 100:
            letras = 'CIEN'
        elif num < 10:
            letras = unidades[num]
        elif num < 30:
            letras = especiales.get(num, decenas[num // 10])
        elif num < 100:
            if num % 10 == 0:
                letras = decenas[num // 10]
            else:
                letras = f"{decenas[num // 10]} Y {unidades[num % 10]}"
        elif num < 1000:
            if num % 100 == 0:
                letras = centenas[num // 100]
            else:
                resto = num % 100
                if resto < 30 and resto in especiales:
                    letras = f"{centenas[num // 100]} {especiales[resto]}"
                elif resto < 10:
                    letras = f"{centenas[num // 100]} {unidades[resto]}"
                elif resto % 10 == 0:
                    letras = f"{centenas[num // 100]} {decenas[resto // 10]}"
                else:
                    letras = f"{centenas[num // 100]} {decenas[resto // 10]} Y {unidades[resto % 10]}"
        else:
            miles = num // 1000
            resto = num % 1000
            if miles == 1:
                letras = 'MIL'
            else:
                letras = f"{unidades[miles]} MIL"
            if resto > 0:
                letras += ' ' + numero_a_letras(resto).replace(' QUETZALES EXACTOS', '').replace(' QUETZALES CON', '')
            letras = letras.strip()
        
        if decimal == 0:
            return f"{letras} QUETZALES EXACTOS"
        else:
            return f"{letras} QUETZALES CON {decimal}/100"
    
    if not mes:
        mes = datetime.now().strftime('%Y-%m')
    
    cliente = Cliente.query.get_or_404(cliente_id)
    
    meses_nombres = {
        '01': 'Enero', '02': 'Febrero', '03': 'Marzo', '04': 'Abril',
        '05': 'Mayo', '06': 'Junio', '07': 'Julio', '08': 'Agosto',
        '09': 'Septiembre', '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre'
    }
    
    try:
        anio, mes_num = mes.split('-')
        mes_nombre = meses_nombres.get(mes_num, mes_num)
    except:
        anio = mes[:4]
        mes_nombre = mes
    
    return render_template('avisos_cobro.html', 
                         clientes=[cliente], 
                         total=cliente.precio_mensual or 0, 
                         mes=mes,
                         mes_nombre=mes_nombre,
                         anio=anio,
                         fecha_emision=datetime.now().strftime('%d-%m-%Y'),
                         numero_a_letras=numero_a_letras)


@app.route('/api/recibos/meses')
def obtener_meses_con_pagos():
    """Obtener lista de meses que tienen pagos registrados"""
    from sqlalchemy import distinct
    
    meses = db.session.query(distinct(Pago.mes_correspondiente)).order_by(Pago.mes_correspondiente.desc()).all()
    meses_list = [m[0] for m in meses if m[0]]
    
    return jsonify({
        'success': True,
        'meses': meses_list
    })



@app.route('/configuracion')
@login_required
def configuracion():
    """Página de configuración de MikroTik"""
    config = ConfigMikroTik.query.first()
    planes = Plan.query.all()
    return render_template('configuracion.html', config=config, planes=planes)

# ============== API MIKROTIK STATUS ==============

@app.route('/api/mikrotik/status')
def mikrotik_status():
    """Verificar estado de conexión a MikroTik (con caché)"""
    global _mikrotik_status_cache
    from datetime import datetime, timedelta
    
    # Si hay caché válido, devolver sin consultar al router
    last_check = _mikrotik_status_cache.get('last_check')
    if last_check and (datetime.now() - last_check).total_seconds() < MIKROTIK_CACHE_TTL:
        return jsonify({
            'success': True,
            'connected': _mikrotik_status_cache['connected'],
            'message': _mikrotik_status_cache['message'],
            'queue_count': _mikrotik_status_cache['queue_count']
        })
    
    try:
        api = get_mikrotik_api()
        if not api:
            _mikrotik_status_cache = {
                'connected': False,
                'message': 'Sin configurar',
                'queue_count': 0,
                'last_check': datetime.now()
            }
            return jsonify({
                'success': True,
                'connected': False,
                'message': 'Sin configurar'
            })
        
        # test_connection devuelve (success, message)
        success, message = api.test_connection()
        if success:
            # Contar queues
            queue_success, queues = api.get_simple_queues()
            queue_count = len(queues) if queue_success and isinstance(queues, list) else 0
            
            _mikrotik_status_cache = {
                'connected': True,
                'message': f'Conectado: {message}',
                'queue_count': queue_count,
                'last_check': datetime.now()
            }
            
            return jsonify({
                'success': True,
                'connected': True,
                'message': f'Conectado: {message}',
                'queue_count': queue_count
            })
        else:
            _mikrotik_status_cache = {
                'connected': False,
                'message': message,
                'queue_count': 0,
                'last_check': datetime.now()
            }
            return jsonify({
                'success': True,
                'connected': False,
                'message': message
            })
    except Exception as e:
        _mikrotik_status_cache = {
            'connected': False,
            'message': str(e)[:50],
            'queue_count': 0,
            'last_check': datetime.now()
        }
        return jsonify({
            'success': True,
            'connected': False,
            'message': str(e)[:50]
        })


# ============== API CLIENTES ==============

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
        
        # Obtener velocidades y precio del plan
        vel_download = data.get('velocidad_download', '10M')
        vel_upload = data.get('velocidad_upload', '5M')
        precio = 0
        
        if data.get('plan_id'):
            plan = Plan.query.get(data['plan_id'])
            if plan:
                vel_download = plan.velocidad_download
                vel_upload = plan.velocidad_upload
                precio = plan.precio
        
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
        
        # Calcular fecha próximo pago
        hoy = datetime.now()
        dia_corte = int(data.get('dia_corte', 1))
        if dia_corte > 28:
            dia_corte = 28
        
        proximo_mes = hoy.month + 1 if hoy.day > dia_corte else hoy.month
        proximo_anio = hoy.year + 1 if proximo_mes > 12 else hoy.year
        if proximo_mes > 12:
            proximo_mes = 1
        
        fecha_proximo_pago = datetime(proximo_anio, proximo_mes, dia_corte)
        
        # Crear cliente en base de datos
        cliente = Cliente(
            nombre=data['nombre'],
            ip_address=data['ip_address'],
            plan=data.get('plan', 'Basico'),
            velocidad_download=vel_download,
            velocidad_upload=vel_upload,
            telefono=data.get('telefono', ''),
            email=data.get('email', ''),
            direccion=data.get('direccion', ''),
            cedula=data.get('cedula', ''),
            queue_name=queue_name,
            mikrotik_id=mikrotik_id,
            estado='activo',
            dia_corte=dia_corte,
            precio_mensual=precio,
            fecha_proximo_pago=fecha_proximo_pago
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


@app.route('/api/cliente/<int:id>', methods=['GET'])
def obtener_cliente(id):
    """Obtener un cliente específico"""
    cliente = Cliente.query.get_or_404(id)
    return jsonify({'success': True, 'cliente': cliente.to_dict()})


@app.route('/api/cliente/<int:id>', methods=['PUT'])
def actualizar_cliente(id):
    """Actualizar cliente existente"""
    try:
        cliente = Cliente.query.get_or_404(id)
        data = request.get_json()
        
        # Actualizar campos básicos
        if data.get('nombre'):
            cliente.nombre = data['nombre']
        if 'telefono' in data:
            cliente.telefono = data['telefono']
        if 'email' in data:
            cliente.email = data['email']
        if 'direccion' in data:
            cliente.direccion = data['direccion']
        if 'cedula' in data:
            cliente.cedula = data['cedula']
        if 'dia_corte' in data:
            cliente.dia_corte = int(data['dia_corte'])
        if 'precio_mensual' in data:
            cliente.precio_mensual = float(data['precio_mensual'])
        
        # Actualizar plan y velocidades
        if data.get('plan_id'):
            plan = Plan.query.get(data['plan_id'])
            if plan:
                cliente.plan = plan.nombre
                cliente.velocidad_download = plan.velocidad_download
                cliente.velocidad_upload = plan.velocidad_upload
                cliente.precio_mensual = plan.precio
                
                # Actualizar en MikroTik
                if cliente.mikrotik_id:
                    api = get_mikrotik_api()
                    if api:
                        api.update_simple_queue(
                            cliente.mikrotik_id,
                            max_limit_download=plan.velocidad_download,
                            max_limit_upload=plan.velocidad_upload
                        )
        
        elif data.get('velocidad_download') or data.get('velocidad_upload'):
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
        
        # Actualizar IP si cambió
        if data.get('ip_address') and data['ip_address'] != cliente.ip_address:
            # Verificar que no exista
            existing = Cliente.query.filter_by(ip_address=data['ip_address']).first()
            if existing and existing.id != id:
                return jsonify({'success': False, 'error': 'Esta IP ya está en uso'}), 400
            
            cliente.ip_address = data['ip_address']
            if cliente.mikrotik_id:
                api = get_mikrotik_api()
                if api:
                    api.update_simple_queue(cliente.mikrotik_id, target=data['ip_address'])
        
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
        
        api = get_mikrotik_api()
        if api:
            # Eliminar queue de MikroTik
            if cliente.mikrotik_id:
                api.delete_simple_queue(cliente.mikrotik_id)
            
            # Remover del address list si estaba cortado
            if cliente.estado == 'cortado':
                api.remove_from_address_list(cliente.ip_address, get_address_list_name())
        
        nombre_cliente = cliente.nombre
        db.session.delete(cliente)
        db.session.commit()
        registrar_auditoria('eliminar', 'cliente', id, f'Cliente eliminado: {nombre_cliente}')
        
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
    """Activar cliente (habilitar queue y remover de address list)"""
    try:
        cliente = Cliente.query.get_or_404(id)
        
        api = get_mikrotik_api()
        if api:
            # Activar queue
            if cliente.mikrotik_id:
                success, msg = api.activate_queue(cliente.mikrotik_id)
                if not success:
                    return jsonify({'success': False, 'error': f'Error MikroTik: {msg}'}), 500
            
            # Remover del address list si estaba cortado
            if cliente.estado == 'cortado':
                api.remove_from_address_list(cliente.ip_address, get_address_list_name())
        
        cliente.estado = 'activo'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Cliente activado'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cliente/<int:id>/cortar', methods=['POST'])
def cortar_cliente(id):
    """Cortar cliente por medio de Address List (bloqueo por firewall)"""
    try:
        cliente = Cliente.query.get_or_404(id)
        
        api = get_mikrotik_api()
        if api:
            # Agregar al address list de morosos
            success, result = api.add_to_address_list(
                cliente.ip_address, 
                get_address_list_name(),
                f"Corte: {cliente.nombre} - {datetime.now().strftime('%Y-%m-%d')}"
            )
            
            if not success:
                return jsonify({'success': False, 'error': f'Error MikroTik: {result}'}), 500
        
        cliente.estado = 'cortado'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Cliente cortado (agregado a Address List)'})
        
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


# ============== API PAGOS ==============

@app.route('/api/pago', methods=['POST'])
def registrar_pago():
    """Registrar un nuevo pago"""
    try:
        data = request.get_json()
        
        cliente_id = data.get('cliente_id')
        if not cliente_id:
            return jsonify({'success': False, 'error': 'Cliente requerido'}), 400
        
        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            return jsonify({'success': False, 'error': 'Cliente no encontrado'}), 404
        
        monto = float(data.get('monto', 0))
        if monto <= 0:
            return jsonify({'success': False, 'error': 'Monto debe ser mayor a 0'}), 400
        
        # Crear pago
        pago = Pago(
            cliente_id=cliente_id,
            monto=monto,
            mes_correspondiente=data.get('mes_correspondiente', datetime.now().strftime('%Y-%m')),
            metodo_pago=data.get('metodo_pago', 'efectivo'),
            referencia=data.get('referencia', ''),
            notas=data.get('notas', ''),
            registrado_por=data.get('registrado_por', 'admin')
        )
        
        db.session.add(pago)
        
        # Actualizar cliente
        cliente.fecha_ultimo_pago = datetime.now()
        cliente.saldo_pendiente = max(0, cliente.saldo_pendiente - monto)
        
        # Calcular nueva fecha de próximo pago
        hoy = datetime.now()
        next_month = hoy.month + 1 if hoy.month < 12 else 1
        next_year = hoy.year if hoy.month < 12 else hoy.year + 1
        dia = min(cliente.dia_corte, 28)
        cliente.fecha_proximo_pago = datetime(next_year, next_month, dia)
        
        # Si estaba cortado o suspendido y pagó, activar automáticamente
        if cliente.estado in ['suspendido', 'cortado'] and data.get('activar_automatico', True):
            api = get_mikrotik_api()
            if api:
                if cliente.mikrotik_id:
                    api.activate_queue(cliente.mikrotik_id)
                if cliente.estado == 'cortado':
                    api.remove_from_address_list(cliente.ip_address, get_address_list_name())
            cliente.estado = 'activo'
        
        db.session.commit()
        registrar_auditoria('pago', 'pago', pago.id, f'Pago Q{monto} de {cliente.nombre}')
        
        return jsonify({
            'success': True, 
            'message': 'Pago registrado exitosamente',
            'pago': pago.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pago/<int:pago_id>', methods=['DELETE'])
@login_required
def eliminar_pago(pago_id):
    """Eliminar un pago registrado"""
    try:
        pago = Pago.query.get(pago_id)
        if not pago:
            return jsonify({'success': False, 'error': 'Pago no encontrado'}), 404
        
        # Revertir el efecto del pago en el cliente
        cliente = Cliente.query.get(pago.cliente_id)
        if cliente:
            cliente.saldo_pendiente = (cliente.saldo_pendiente or 0) + pago.monto
        
        cliente_nombre = cliente.nombre if cliente else 'Desconocido'
        monto_pago = pago.monto
        db.session.delete(pago)
        db.session.commit()
        registrar_auditoria('eliminar', 'pago', pago_id, f'Pago Q{monto_pago} eliminado de {cliente_nombre}')
        
        return jsonify({'success': True, 'message': 'Pago eliminado exitosamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pagos', methods=['GET'])
def obtener_pagos():
    """Obtener lista de pagos"""
    cliente_id = request.args.get('cliente_id')
    
    query = Pago.query.order_by(Pago.fecha_pago.desc())
    
    if cliente_id:
        query = query.filter_by(cliente_id=cliente_id)
    
    pagos = query.limit(100).all()
    
    return jsonify({
        'success': True,
        'pagos': [p.to_dict() for p in pagos]
    })


@app.route('/api/pagos/cliente/<int:cliente_id>', methods=['GET'])
def obtener_pagos_cliente(cliente_id):
    """Obtener historial de pagos de un cliente"""
    pagos = Pago.query.filter_by(cliente_id=cliente_id).order_by(Pago.fecha_pago.desc()).all()
    return jsonify({
        'success': True,
        'pagos': [p.to_dict() for p in pagos]
    })


# ============== IMPORTAR/EXPORTAR EXCEL ==============

@app.route('/api/clientes/exportar', methods=['GET'])
def exportar_clientes():
    """Exportar clientes a Excel"""
    try:
        # Intentar usar openpyxl
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
        except ImportError:
            # Si no está instalado, exportar como CSV
            return exportar_clientes_csv()
        
        clientes = Cliente.query.order_by(Cliente.nombre).all()
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Clientes"
        
        # Encabezados
        headers = ['ID', 'Nombre', 'IP', 'Plan', 'Velocidad Bajada', 'Velocidad Subida', 
                   'Telefono', 'Email', 'Direccion', 'Cedula', 'Estado', 'Dia Corte',
                   'Precio Mensual', 'Fecha Registro']
        
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        # Datos
        for row, cliente in enumerate(clientes, 2):
            ws.cell(row=row, column=1, value=cliente.id)
            ws.cell(row=row, column=2, value=cliente.nombre)
            ws.cell(row=row, column=3, value=cliente.ip_address)
            ws.cell(row=row, column=4, value=cliente.plan)
            ws.cell(row=row, column=5, value=cliente.velocidad_download)
            ws.cell(row=row, column=6, value=cliente.velocidad_upload)
            ws.cell(row=row, column=7, value=cliente.telefono)
            ws.cell(row=row, column=8, value=cliente.email)
            ws.cell(row=row, column=9, value=cliente.direccion)
            ws.cell(row=row, column=10, value=cliente.cedula)
            ws.cell(row=row, column=11, value=cliente.estado)
            ws.cell(row=row, column=12, value=cliente.dia_corte)
            ws.cell(row=row, column=13, value=cliente.precio_mensual)
            ws.cell(row=row, column=14, value=cliente.fecha_registro.strftime('%Y-%m-%d') if cliente.fecha_registro else '')
        
        # Ajustar anchos de columna
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width
        
        # Guardar en memoria
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'clientes_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def exportar_clientes_csv():
    """Exportar clientes a CSV (fallback)"""
    import csv
    from io import StringIO
    
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Encabezados
    writer.writerow(['ID', 'Nombre', 'IP', 'Plan', 'Velocidad Bajada', 'Velocidad Subida', 
                     'Telefono', 'Email', 'Direccion', 'Cedula', 'Estado', 'Dia Corte',
                     'Precio Mensual', 'Fecha Registro'])
    
    # Datos
    for cliente in clientes:
        writer.writerow([
            cliente.id, cliente.nombre, cliente.ip_address, cliente.plan,
            cliente.velocidad_download, cliente.velocidad_upload, cliente.telefono,
            cliente.email, cliente.direccion, cliente.cedula, cliente.estado,
            cliente.dia_corte, cliente.precio_mensual,
            cliente.fecha_registro.strftime('%Y-%m-%d') if cliente.fecha_registro else ''
        ])
    
    output.seek(0)
    return send_file(
        BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'clientes_{datetime.now().strftime("%Y%m%d")}.csv'
    )


@app.route('/api/clientes/importar', methods=['POST'])
def importar_clientes():
    """Importar clientes desde archivo Excel o CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió archivo'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400
        
        filename = file.filename.lower()
        
        clientes_importados = 0
        clientes_omitidos = 0
        errores = []
        
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            # Importar desde Excel
            try:
                from openpyxl import load_workbook
                
                wb = load_workbook(file)
                ws = wb.active
                
                # Obtener encabezados y normalizarlos
                raw_headers = [cell.value if cell.value else '' for cell in ws[1]]
                headers = [str(h).lower().strip() for h in raw_headers]
                
                for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
                    try:
                        data = dict(zip(headers, row))
                        
                        # Buscar nombre con varias variantes
                        nombre = (data.get('nombre', '') or 
                                 data.get('nombre del cliente', '') or 
                                 data.get('nombre cliente', '') or 
                                 data.get('cliente', ''))
                        
                        # Buscar IP con varias variantes
                        ip = (data.get('ip', '') or 
                             data.get('ip_address', '') or 
                             data.get('ip address', '') or
                             data.get('direccion ip', ''))
                        
                        if not nombre or not ip:
                            clientes_omitidos += 1
                            errores.append(f"Fila {row_num}: Falta nombre o IP")
                            continue
                        
                        # Verificar si ya existe
                        if Cliente.query.filter_by(ip_address=str(ip)).first():
                            clientes_omitidos += 1
                            errores.append(f"Fila {row_num}: IP {ip} ya existe")
                            continue
                        
                        # Obtener plan
                        plan = (data.get('plan', '') or 'Basico')
                        
                        # Obtener velocidades
                        vel_down = (data.get('velocidad download', '') or 
                                   data.get('velocidad bajada', '') or 
                                   data.get('velocidad_download', '') or 
                                   data.get('download', '') or '10M')
                        vel_up = (data.get('velocidad upload', '') or 
                                 data.get('velocidad subida', '') or 
                                 data.get('velocidad_upload', '') or 
                                 data.get('upload', '') or '5M')
                        
                        # Obtener otros datos
                        telefono = data.get('telefono', '') or data.get('teléfono', '') or ''
                        email = data.get('email', '') or data.get('correo', '') or ''
                        direccion = data.get('direccion', '') or data.get('dirección', '') or ''
                        cedula = (data.get('cedula', '') or 
                                 data.get('cédula', '') or 
                                 data.get('cedula/dpi', '') or 
                                 data.get('dpi', '') or '')
                        
                        # Obtener día de corte
                        dia_corte_raw = (data.get('dia de corte', '') or 
                                        data.get('dia corte', '') or 
                                        data.get('dia_corte', '') or 
                                        data.get('día de corte', '') or 1)
                        try:
                            dia_corte = int(dia_corte_raw) if dia_corte_raw else 1
                        except:
                            dia_corte = 1
                        
                        # Obtener precio
                        precio_raw = (data.get('precio mensual (q)', '') or 
                                     data.get('precio mensual', '') or 
                                     data.get('precio_mensual', '') or 
                                     data.get('precio', '') or 0)
                        try:
                            precio = float(precio_raw) if precio_raw else 0
                        except:
                            precio = 0
                        
                        # Generar nombre del queue
                        nombre_limpio = str(nombre).replace(' ', '-').lower()[:30]
                        queue_name = f"cliente-{nombre_limpio}-{str(ip).replace('.', '-')}"
                        
                        # Crear Simple Queue en MikroTik
                        mikrotik_id = None
                        api = get_mikrotik_api()
                        
                        if api:
                            success, result = api.create_simple_queue(
                                name=queue_name,
                                target=str(ip),
                                max_limit_download=str(vel_down) if vel_down else '10M',
                                max_limit_upload=str(vel_up) if vel_up else '5M',
                                comment=f"Cliente: {nombre}"
                            )
                            
                            if success:
                                mikrotik_id = result
                            else:
                                errores.append(f"Fila {row_num}: Queue no creado - {result}")
                        
                        cliente = Cliente(
                            nombre=str(nombre),
                            ip_address=str(ip),
                            plan=str(plan) if plan else 'Basico',
                            velocidad_download=str(vel_down) if vel_down else '10M',
                            velocidad_upload=str(vel_up) if vel_up else '5M',
                            telefono=str(telefono) if telefono else '',
                            email=str(email) if email else '',
                            direccion=str(direccion) if direccion else '',
                            cedula=str(cedula) if cedula else '',
                            estado='activo',
                            dia_corte=dia_corte,
                            precio_mensual=precio,
                            queue_name=queue_name,
                            mikrotik_id=mikrotik_id
                        )
                        
                        db.session.add(cliente)
                        clientes_importados += 1
                        
                    except Exception as e:
                        errores.append(f"Fila {row_num}: {str(e)}")
                        clientes_omitidos += 1
                
            except ImportError:
                return jsonify({'success': False, 'error': 'Libreria openpyxl no instalada'}), 500
        
        elif filename.endswith('.csv'):
            # Importar desde CSV
            import csv
            from io import StringIO
            
            content = file.read().decode('utf-8')
            reader = csv.DictReader(StringIO(content))
            
            for row_num, row in enumerate(reader, 2):
                try:
                    # Normalizar nombres de columnas
                    data = {k.lower(): v for k, v in row.items()}
                    
                    nombre = data.get('nombre', '')
                    ip = data.get('ip', data.get('ip_address', ''))
                    
                    if not nombre or not ip:
                        clientes_omitidos += 1
                        continue
                    
                    # Verificar si ya existe
                    if Cliente.query.filter_by(ip_address=ip).first():
                        clientes_omitidos += 1
                        continue
                    
                    cliente = Cliente(
                        nombre=nombre,
                        ip_address=ip,
                        plan=data.get('plan', 'Basico'),
                        velocidad_download=data.get('velocidad bajada', data.get('velocidad_download', '10M')),
                        velocidad_upload=data.get('velocidad subida', data.get('velocidad_upload', '5M')),
                        telefono=data.get('telefono', ''),
                        email=data.get('email', ''),
                        direccion=data.get('direccion', ''),
                        cedula=data.get('cedula', ''),
                        estado='activo',
                        dia_corte=int(data.get('dia corte', data.get('dia_corte', 1)) or 1),
                        precio_mensual=float(data.get('precio mensual', data.get('precio_mensual', 0)) or 0)
                    )
                    
                    db.session.add(cliente)
                    clientes_importados += 1
                    
                except Exception as e:
                    errores.append(f"Fila {row_num}: {str(e)}")
                    clientes_omitidos += 1
        
        else:
            return jsonify({'success': False, 'error': 'Formato no soportado. Use .xlsx, .xls o .csv'}), 400
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Importación completada',
            'importados': clientes_importados,
            'omitidos': clientes_omitidos,
            'errores': errores[:10]  # Solo mostrar primeros 10 errores
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== REPORTES ==============

@app.route('/api/reportes/resumen', methods=['GET'])
def reporte_resumen():
    """Reporte resumen general"""
    try:
        total_clientes = Cliente.query.count()
        clientes_activos = Cliente.query.filter_by(estado='activo').count()
        clientes_suspendidos = Cliente.query.filter_by(estado='suspendido').count()
        clientes_cortados = Cliente.query.filter_by(estado='cortado').count()
        
        # Pagos del mes
        hoy = datetime.now()
        primer_dia_mes = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pagos_mes = Pago.query.filter(Pago.fecha_pago >= primer_dia_mes).all()
        total_recaudado = sum(p.monto for p in pagos_mes)
        
        # Proyección mensual
        total_mensual_esperado = db.session.query(db.func.sum(Cliente.precio_mensual)).filter(
            Cliente.estado == 'activo'
        ).scalar() or 0
        
        # Clientes por plan
        from sqlalchemy import func
        clientes_por_plan = db.session.query(
            Cliente.plan, 
            func.count(Cliente.id)
        ).group_by(Cliente.plan).all()
        
        return jsonify({
            'success': True,
            'data': {
                'total_clientes': total_clientes,
                'clientes_activos': clientes_activos,
                'clientes_suspendidos': clientes_suspendidos,
                'clientes_cortados': clientes_cortados,
                'total_recaudado_mes': total_recaudado,
                'total_mensual_esperado': total_mensual_esperado,
                'porcentaje_recaudado': (total_recaudado / total_mensual_esperado * 100) if total_mensual_esperado > 0 else 0,
                'clientes_por_plan': [{'plan': p[0], 'cantidad': p[1]} for p in clientes_por_plan]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reportes/pagos-mensuales', methods=['GET'])
def reporte_pagos_mensuales():
    """Reporte de pagos por mes"""
    try:
        from sqlalchemy import func, extract
        
        # Últimos 12 meses
        pagos_por_mes = db.session.query(
            func.strftime('%Y-%m', Pago.fecha_pago).label('mes'),
            func.sum(Pago.monto).label('total'),
            func.count(Pago.id).label('cantidad')
        ).group_by(
            func.strftime('%Y-%m', Pago.fecha_pago)
        ).order_by(
            func.strftime('%Y-%m', Pago.fecha_pago).desc()
        ).limit(12).all()
        
        return jsonify({
            'success': True,
            'data': [{
                'mes': p.mes,
                'total': p.total,
                'cantidad': p.cantidad
            } for p in pagos_por_mes]
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== RECIBOS ==============

@app.route('/api/recibo/<int:pago_id>', methods=['GET'])
def generar_recibo(pago_id):
    """Generar recibo de pago (HTML para imprimir)"""
    try:
        pago = Pago.query.get_or_404(pago_id)
        cliente = pago.cliente
        
        return render_template('recibo.html', pago=pago, cliente=cliente)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
        config.address_list_cortados = data.get('address_list_cortados', 'MOROSOS')
        config.activo = True
        
        db.session.add(config)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Configuracion guardada'})
        
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
                'message': f'Conexion exitosa a: {result}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Error de conexion: {result}'
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


@app.route('/api/plan/<int:id>', methods=['PUT'])
def editar_plan(id):
    """Editar plan existente"""
    try:
        plan = Plan.query.get_or_404(id)
        data = request.get_json()
        
        plan.nombre = data.get('nombre', plan.nombre)
        plan.velocidad_download = data.get('velocidad_download', plan.velocidad_download)
        plan.velocidad_upload = data.get('velocidad_upload', plan.velocidad_upload)
        plan.precio = float(data.get('precio', plan.precio))
        plan.descripcion = data.get('descripcion', plan.descripcion)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Plan actualizado'})
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


@app.route('/api/sync/import-queues', methods=['POST'])
def importar_queues_mikrotik():
    """Importa los queues de MikroTik como clientes en la base de datos"""
    try:
        api = get_mikrotik_api()
        if not api:
            return jsonify({'success': False, 'error': 'MikroTik no configurado'}), 400
        
        success, queues = api.get_simple_queues()
        
        if not success:
            return jsonify({'success': False, 'error': f'Error al obtener queues: {queues}'}), 500
        
        importados = 0
        omitidos = 0
        errores = []
        
        for queue in queues:
            try:
                # Extraer datos del queue
                nombre = queue.get('name', '')
                target = queue.get('target', '')
                max_limit = queue.get('max-limit', '10M/10M')
                comment = queue.get('comment', '')
                queue_id = queue.get('.id', '')
                disabled = queue.get('disabled', 'false') == 'true'
                
                # Extraer IP del target (formato: IP/32 o IP)
                ip_address = target.replace('/32', '').strip()
                
                # Validar IP
                if not ip_address or not ip_address.replace('.', '').isdigit() or ip_address.count('.') != 3:
                    continue
                
                # Verificar si ya existe un cliente con esa IP
                cliente_existente = Cliente.query.filter_by(ip_address=ip_address).first()
                if cliente_existente:
                    omitidos += 1
                    continue
                
                # Parsear velocidades (formato: upload/download)
                velocidades = max_limit.split('/')
                vel_upload = velocidades[0] if len(velocidades) > 0 else '5M'
                vel_download = velocidades[1] if len(velocidades) > 1 else '10M'
                
                # Crear nuevo cliente
                nuevo_cliente = Cliente(
                    nombre=nombre,
                    ip_address=ip_address,
                    plan=comment if comment else 'Importado de MikroTik',
                    velocidad_download=vel_download,
                    velocidad_upload=vel_upload,
                    estado='activo' if not disabled else 'suspendido',
                    queue_id=queue_id,
                    queue_name=nombre
                )
                
                db.session.add(nuevo_cliente)
                importados += 1
                
            except Exception as e:
                errores.append(f"{nombre}: {str(e)}")
                continue
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'importados': importados,
            'omitidos': omitidos,
            'errores': errores[:5] if errores else [],
            'message': f'Se importaron {importados} clientes desde MikroTik. {omitidos} omitidos (ya existían).'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== INICIALIZAR DB ==============

def migrate_db():
    """Agrega columnas faltantes a tablas existentes"""
    from sqlalchemy import text, inspect
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Verificar si la tabla clientes existe
        if 'clientes' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('clientes')]
            
            # Columnas a agregar si no existen
            columns_to_add = {
                'email': 'VARCHAR(100)',
                'cedula': 'VARCHAR(20)',
                'dia_corte': 'INTEGER DEFAULT 1',
                'fecha_ultimo_pago': 'DATETIME',
                'fecha_proximo_pago': 'DATETIME',
                'precio_mensual': 'FLOAT DEFAULT 0',
                'saldo_pendiente': 'FLOAT DEFAULT 0',
                'latitud': 'FLOAT',
                'longitud': 'FLOAT',
            }
            
            for col_name, col_type in columns_to_add.items():
                if col_name not in existing_columns:
                    try:
                        db.session.execute(text(f'ALTER TABLE clientes ADD COLUMN {col_name} {col_type}'))
                        db.session.commit()
                        print(f"[MIGRATION] Columna '{col_name}' agregada a clientes")
                    except Exception as e:
                        db.session.rollback()
                        print(f"[MIGRATION] Error agregando '{col_name}': {e}")
        
        # Verificar si la tabla config_mikrotik existe
        if 'config_mikrotik' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('config_mikrotik')]
            
            if 'address_list_cortados' not in existing_columns:
                try:
                    db.session.execute(text("ALTER TABLE config_mikrotik ADD COLUMN address_list_cortados VARCHAR(50) DEFAULT 'MOROSOS'"))
                    db.session.commit()
                    print("[MIGRATION] Columna 'address_list_cortados' agregada")
                except Exception as e:
                    db.session.rollback()
                    print(f"[MIGRATION] Error: {e}")


def init_db():
    """Inicializar base de datos y crear tablas"""
    with app.app_context():
        # Primero crear tablas nuevas
        db.create_all()
        
        # Luego migrar columnas faltantes
        migrate_db()
        
        # Crear usuario admin por defecto si no existe
        if Usuario.query.count() == 0:
            admin = Usuario(username='admin', nombre='Administrador', rol='admin')
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
            print("[OK] Usuario admin creado (user: admin, pass: admin)")
        
        # Crear planes por defecto si no existen
        if Plan.query.count() == 0:
            planes_default = [
                Plan(nombre='Basico 5Mbps', velocidad_download='5M', velocidad_upload='2M', precio=15.00),
                Plan(nombre='Estandar 10Mbps', velocidad_download='10M', velocidad_upload='5M', precio=25.00),
                Plan(nombre='Premium 20Mbps', velocidad_download='20M', velocidad_upload='10M', precio=35.00),
                Plan(nombre='Ultra 50Mbps', velocidad_download='50M', velocidad_upload='25M', precio=50.00),
                Plan(nombre='Empresarial 100Mbps', velocidad_download='100M', velocidad_upload='50M', precio=100.00),
            ]
            for plan in planes_default:
                db.session.add(plan)
            db.session.commit()
            print("[OK] Planes por defecto creados")
        
        print("[OK] Base de datos inicializada")


# ============== API DASHBOARD CHARTS ==============

@app.route('/api/dashboard/charts')
@login_required
def dashboard_charts():
    """Datos para las gráficas del dashboard"""
    from sqlalchemy import func, extract
    
    hoy = datetime.now()
    
    # Ingresos últimos 6 meses
    ingresos_mensuales = []
    for i in range(5, -1, -1):
        fecha = hoy - timedelta(days=30*i)
        mes = fecha.month
        anio = fecha.year
        total = db.session.query(func.coalesce(func.sum(Pago.monto), 0)).filter(
            extract('month', Pago.fecha_pago) == mes,
            extract('year', Pago.fecha_pago) == anio
        ).scalar()
        nombre_mes = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][mes-1]
        ingresos_mensuales.append({'mes': f'{nombre_mes} {anio}', 'total': float(total)})
    
    # Distribución por plan
    planes_dist = db.session.query(
        Cliente.plan, func.count(Cliente.id)
    ).group_by(Cliente.plan).all()
    
    # Distribución por estado
    estados = db.session.query(
        Cliente.estado, func.count(Cliente.id)
    ).group_by(Cliente.estado).all()
    
    # Clientes nuevos por mes (últimos 6 meses)
    clientes_nuevos = []
    for i in range(5, -1, -1):
        fecha = hoy - timedelta(days=30*i)
        mes = fecha.month
        anio = fecha.year
        total = db.session.query(func.count(Cliente.id)).filter(
            extract('month', Cliente.fecha_registro) == mes,
            extract('year', Cliente.fecha_registro) == anio
        ).scalar()
        nombre_mes = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'][mes-1]
        clientes_nuevos.append({'mes': f'{nombre_mes} {anio}', 'total': int(total)})
    
    return jsonify({
        'success': True,
        'ingresos_mensuales': ingresos_mensuales,
        'planes_distribucion': [{'plan': p[0], 'cantidad': p[1]} for p in planes_dist],
        'estados_distribucion': [{'estado': e[0], 'cantidad': e[1]} for e in estados],
        'clientes_nuevos': clientes_nuevos
    })


# ============== AUDIT LOG ==============

@app.route('/actividad')
@login_required
def actividad_view():
    """Página de registro de actividad"""
    logs = AuditLog.query.order_by(AuditLog.fecha.desc()).limit(200).all()
    return render_template('actividad.html', logs=logs)


@app.route('/api/actividad')
@login_required
def api_actividad():
    """API para obtener registros de auditoría"""
    limit = request.args.get('limit', 100, type=int)
    logs = AuditLog.query.order_by(AuditLog.fecha.desc()).limit(limit).all()
    return jsonify({'success': True, 'logs': [l.to_dict() for l in logs]})


# ============== MAPA DE CLIENTES ==============

@app.route('/mapa')
@login_required
def mapa_view():
    """Página del mapa de clientes"""
    return render_template('mapa.html')


@app.route('/api/clientes/mapa')
@login_required
def api_clientes_mapa():
    """Obtener clientes con coordenadas para el mapa"""
    clientes = Cliente.query.filter(
        Cliente.latitud.isnot(None),
        Cliente.longitud.isnot(None)
    ).all()
    return jsonify({
        'success': True,
        'clientes': [{
            'id': c.id,
            'nombre': c.nombre,
            'ip_address': c.ip_address,
            'plan': c.plan,
            'estado': c.estado,
            'latitud': c.latitud,
            'longitud': c.longitud,
            'telefono': c.telefono,
            'direccion': c.direccion
        } for c in clientes]
    })


@app.route('/api/cliente/<int:id>/ubicacion', methods=['PUT'])
@login_required
def actualizar_ubicacion(id):
    """Actualizar coordenadas de un cliente"""
    try:
        cliente = Cliente.query.get_or_404(id)
        data = request.get_json()
        cliente.latitud = data.get('latitud')
        cliente.longitud = data.get('longitud')
        db.session.commit()
        registrar_auditoria('editar', 'cliente', id, f'Ubicación actualizada: {cliente.nombre}')
        return jsonify({'success': True, 'message': 'Ubicación actualizada'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== MONITOR ANCHO DE BANDA ==============

@app.route('/monitor')
@login_required
def monitor_view():
    """Página de monitoreo de ancho de banda"""
    return render_template('monitor.html')


@app.route('/api/monitor/bandwidth')
@login_required
def api_bandwidth():
    """Obtener estadísticas de bandwidth desde MikroTik"""
    api = get_mikrotik_api()
    if not api:
        return jsonify({'success': False, 'error': 'MikroTik no configurado'})
    
    try:
        success, queues = api.get_simple_queues()
        if not success:
            return jsonify({'success': False, 'error': 'No se pudo obtener datos de MikroTik'})
        
        result = []
        for q in queues:
            # MikroTik devuelve bytes como "upload/download"
            rate = q.get('rate', '0/0').split('/')
            bytes_data = q.get('bytes', '0/0').split('/')
            
            upload_rate = int(rate[0]) if len(rate) > 0 and rate[0].isdigit() else 0
            download_rate = int(rate[1]) if len(rate) > 1 and rate[1].isdigit() else 0
            upload_bytes = int(bytes_data[0]) if len(bytes_data) > 0 and bytes_data[0].isdigit() else 0
            download_bytes = int(bytes_data[1]) if len(bytes_data) > 1 and bytes_data[1].isdigit() else 0
            
            max_limit = q.get('max-limit', '0/0').split('/')
            max_upload = max_limit[0] if len(max_limit) > 0 else '0'
            max_download = max_limit[1] if len(max_limit) > 1 else '0'
            
            result.append({
                'name': q.get('name', ''),
                'target': q.get('target', ''),
                'disabled': q.get('disabled', 'false') == 'true',
                'upload_rate': upload_rate,
                'download_rate': download_rate,
                'upload_bytes': upload_bytes,
                'download_bytes': download_bytes,
                'max_limit': q.get('max-limit', '0/0'),
                'max_upload': max_upload,
                'max_download': max_download,
                'comment': q.get('comment', '')
            })
        
        return jsonify({'success': True, 'queues': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============== BACKUP ==============

@app.route('/api/backup', methods=['GET'])
@login_required
def descargar_backup():
    """Descargar backup de la base de datos SQLite"""
    try:
        db_path = os.path.join(app.instance_path, 'clientes.db')
        if not os.path.exists(db_path):
            return jsonify({'success': False, 'error': 'Archivo de base de datos no encontrado'}), 404
        
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_archivo = f'cuzonet_backup_{fecha}.db'
        
        return send_file(
            db_path,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/x-sqlite3'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/completo', methods=['GET'])
@login_required
def descargar_backup_completo():
    """Descargar backup completo de TODOS los datos en formato ZIP con JSONs"""
    try:
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # ---- Clientes ----
        clientes = Cliente.query.all()
        clientes_data = [c.to_dict() for c in clientes]
        
        # ---- Pagos ----
        pagos = Pago.query.all()
        pagos_data = [p.to_dict() for p in pagos]
        
        # ---- Planes ----
        planes = Plan.query.all()
        planes_data = [{
            'id': p.id,
            'nombre': p.nombre,
            'velocidad_download': p.velocidad_download,
            'velocidad_upload': p.velocidad_upload,
            'precio': p.precio,
            'descripcion': p.descripcion
        } for p in planes]
        
        # ---- Configuración MikroTik ----
        configs = ConfigMikroTik.query.all()
        configs_data = [{
            'id': c.id,
            'nombre': c.nombre,
            'host': c.host,
            'port': c.port,
            'username': c.username,
            'use_ssl': c.use_ssl,
            'address_list_cortados': c.address_list_cortados
        } for c in configs]
        
        # ---- Registro de Actividad ----
        logs = AuditLog.query.order_by(AuditLog.fecha.desc()).all()
        logs_data = [l.to_dict() for l in logs]
        
        # ---- Usuarios (sin contraseñas) ----
        usuarios = Usuario.query.all()
        usuarios_data = [{
            'id': u.id,
            'username': u.username,
            'nombre': u.nombre,
            'rol': u.rol,
            'activo': u.activo,
            'fecha_creacion': u.fecha_creacion.strftime('%Y-%m-%d %H:%M') if u.fecha_creacion else None
        } for u in usuarios]
        
        # ---- Resumen general ----
        resumen = {
            'fecha_backup': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_clientes': len(clientes_data),
            'total_pagos': len(pagos_data),
            'total_planes': len(planes_data),
            'total_usuarios': len(usuarios_data),
            'total_registros_actividad': len(logs_data),
            'clientes_activos': len([c for c in clientes_data if c.get('estado') == 'activo']),
            'clientes_suspendidos': len([c for c in clientes_data if c.get('estado') == 'suspendido']),
            'clientes_cortados': len([c for c in clientes_data if c.get('estado') == 'cortado']),
        }
        
        # Crear ZIP en memoria
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('resumen_backup.json', json.dumps(resumen, indent=2, ensure_ascii=False))
            zf.writestr('clientes.json', json.dumps(clientes_data, indent=2, ensure_ascii=False))
            zf.writestr('pagos.json', json.dumps(pagos_data, indent=2, ensure_ascii=False))
            zf.writestr('planes.json', json.dumps(planes_data, indent=2, ensure_ascii=False))
            zf.writestr('configuracion_mikrotik.json', json.dumps(configs_data, indent=2, ensure_ascii=False))
            zf.writestr('registro_actividad.json', json.dumps(logs_data, indent=2, ensure_ascii=False))
            zf.writestr('usuarios.json', json.dumps(usuarios_data, indent=2, ensure_ascii=False))
            
            # También incluir la base de datos SQLite si existe
            db_path = os.path.join(app.instance_path, 'clientes.db')
            if os.path.exists(db_path):
                zf.write(db_path, 'clientes.db')
        
        zip_buffer.seek(0)
        nombre_archivo = f'cuzonet_backup_completo_{fecha}.zip'
        
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/zip'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/backup/info', methods=['GET'])
@login_required
def backup_info():
    """Obtener información de lo que incluiría el backup"""
    try:
        total_clientes = Cliente.query.count()
        total_pagos = Pago.query.count()
        total_planes = Plan.query.count()
        total_logs = AuditLog.query.count()
        total_usuarios = Usuario.query.count()
        
        return jsonify({
            'success': True,
            'info': {
                'clientes': total_clientes,
                'pagos': total_pagos,
                'planes': total_planes,
                'registros_actividad': total_logs,
                'usuarios': total_usuarios
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/backup/restaurar', methods=['POST'])
@login_required
def restaurar_backup():
    """Restaurar datos desde un archivo ZIP de backup completo"""
    try:
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió ningún archivo'}), 400
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            return jsonify({'success': False, 'error': 'No se seleccionó ningún archivo'}), 400
        
        if not archivo.filename.lower().endswith('.zip'):
            return jsonify({'success': False, 'error': 'El archivo debe ser un ZIP de backup (.zip)'}), 400
        
        # Leer el ZIP en memoria
        zip_data = BytesIO(archivo.read())
        
        if not zipfile.is_zipfile(zip_data):
            return jsonify({'success': False, 'error': 'El archivo no es un ZIP válido'}), 400
        
        zip_data.seek(0)
        resultados = {
            'clientes_importados': 0,
            'pagos_importados': 0,
            'planes_importados': 0,
            'config_importada': False,
            'errores': []
        }
        
        with zipfile.ZipFile(zip_data, 'r') as zf:
            archivos_en_zip = zf.namelist()
            
            # ---- Restaurar Planes ----
            if 'planes.json' in archivos_en_zip:
                try:
                    planes_data = json.loads(zf.read('planes.json').decode('utf-8'))
                    for p in planes_data:
                        existente = Plan.query.filter_by(nombre=p['nombre']).first()
                        if not existente:
                            nuevo = Plan(
                                nombre=p['nombre'],
                                velocidad_download=p['velocidad_download'],
                                velocidad_upload=p['velocidad_upload'],
                                precio=p.get('precio', 0),
                                descripcion=p.get('descripcion', '')
                            )
                            db.session.add(nuevo)
                            resultados['planes_importados'] += 1
                        else:
                            existente.velocidad_download = p['velocidad_download']
                            existente.velocidad_upload = p['velocidad_upload']
                            existente.precio = p.get('precio', 0)
                            existente.descripcion = p.get('descripcion', '')
                            resultados['planes_importados'] += 1
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    resultados['errores'].append(f'Error en planes: {str(e)}')
            
            # ---- Restaurar Configuración MikroTik ----
            if 'configuracion_mikrotik.json' in archivos_en_zip:
                try:
                    configs_data = json.loads(zf.read('configuracion_mikrotik.json').decode('utf-8'))
                    for c in configs_data:
                        existente = ConfigMikroTik.query.first()
                        if existente:
                            existente.host = c.get('host', '')
                            existente.port = c.get('port', 80)
                            existente.username = c.get('username', '')
                            existente.use_ssl = c.get('use_ssl', False)
                            existente.address_list_cortados = c.get('address_list_cortados', 'MOROSOS')
                        else:
                            nueva = ConfigMikroTik(
                                nombre=c.get('nombre', 'Principal'),
                                host=c.get('host', ''),
                                port=c.get('port', 80),
                                username=c.get('username', ''),
                                password='',
                                use_ssl=c.get('use_ssl', False),
                                address_list_cortados=c.get('address_list_cortados', 'MOROSOS')
                            )
                            db.session.add(nueva)
                        resultados['config_importada'] = True
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    resultados['errores'].append(f'Error en config: {str(e)}')
            
            # ---- Restaurar Clientes ----
            if 'clientes.json' in archivos_en_zip:
                try:
                    clientes_data = json.loads(zf.read('clientes.json').decode('utf-8'))
                    for c in clientes_data:
                        existente = Cliente.query.filter_by(ip_address=c['ip_address']).first()
                        if not existente:
                            nuevo = Cliente(
                                nombre=c['nombre'],
                                ip_address=c['ip_address'],
                                plan=c['plan'],
                                velocidad_download=c['velocidad_download'],
                                velocidad_upload=c['velocidad_upload'],
                                telefono=c.get('telefono', ''),
                                email=c.get('email', ''),
                                direccion=c.get('direccion', ''),
                                cedula=c.get('cedula', ''),
                                estado=c.get('estado', 'activo'),
                                queue_name=c.get('queue_name', ''),
                                mikrotik_id=c.get('mikrotik_id', ''),
                                dia_corte=c.get('dia_corte', 1),
                                precio_mensual=c.get('precio_mensual', 0),
                                saldo_pendiente=c.get('saldo_pendiente', 0),
                                latitud=c.get('latitud'),
                                longitud=c.get('longitud')
                            )
                            if c.get('fecha_ultimo_pago'):
                                try:
                                    nuevo.fecha_ultimo_pago = datetime.strptime(c['fecha_ultimo_pago'], '%Y-%m-%d')
                                except:
                                    pass
                            if c.get('fecha_proximo_pago'):
                                try:
                                    nuevo.fecha_proximo_pago = datetime.strptime(c['fecha_proximo_pago'], '%Y-%m-%d')
                                except:
                                    pass
                            db.session.add(nuevo)
                            resultados['clientes_importados'] += 1
                        else:
                            # Actualizar datos del cliente existente
                            existente.nombre = c['nombre']
                            existente.plan = c['plan']
                            existente.velocidad_download = c['velocidad_download']
                            existente.velocidad_upload = c['velocidad_upload']
                            existente.telefono = c.get('telefono', '')
                            existente.email = c.get('email', '')
                            existente.direccion = c.get('direccion', '')
                            existente.cedula = c.get('cedula', '')
                            existente.estado = c.get('estado', 'activo')
                            existente.dia_corte = c.get('dia_corte', 1)
                            existente.precio_mensual = c.get('precio_mensual', 0)
                            existente.saldo_pendiente = c.get('saldo_pendiente', 0)
                            existente.latitud = c.get('latitud')
                            existente.longitud = c.get('longitud')
                            resultados['clientes_importados'] += 1
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    resultados['errores'].append(f'Error en clientes: {str(e)}')
            
            # ---- Restaurar Pagos ----
            if 'pagos.json' in archivos_en_zip:
                try:
                    pagos_data = json.loads(zf.read('pagos.json').decode('utf-8'))
                    for p in pagos_data:
                        # Buscar cliente por nombre
                        cliente = None
                        if p.get('cliente_nombre'):
                            cliente = Cliente.query.filter_by(nombre=p['cliente_nombre']).first()
                        if not cliente and p.get('cliente_id'):
                            cliente = Cliente.query.get(p['cliente_id'])
                        
                        if cliente:
                            # Verificar si el pago ya existe (por fecha y monto y cliente)
                            fecha_pago = None
                            if p.get('fecha_pago'):
                                try:
                                    fecha_pago = datetime.strptime(p['fecha_pago'], '%Y-%m-%d %H:%M')
                                except:
                                    try:
                                        fecha_pago = datetime.strptime(p['fecha_pago'], '%Y-%m-%d')
                                    except:
                                        fecha_pago = datetime.utcnow()
                            
                            pago_existente = None
                            if fecha_pago:
                                pago_existente = Pago.query.filter_by(
                                    cliente_id=cliente.id,
                                    monto=p['monto'],
                                    mes_correspondiente=p.get('mes_correspondiente', '')
                                ).filter(
                                    db.func.date(Pago.fecha_pago) == fecha_pago.date()
                                ).first()
                            
                            if not pago_existente:
                                nuevo_pago = Pago(
                                    cliente_id=cliente.id,
                                    monto=p['monto'],
                                    fecha_pago=fecha_pago or datetime.utcnow(),
                                    mes_correspondiente=p.get('mes_correspondiente', ''),
                                    metodo_pago=p.get('metodo_pago', ''),
                                    referencia=p.get('referencia', ''),
                                    notas=p.get('notas', '')
                                )
                                db.session.add(nuevo_pago)
                                resultados['pagos_importados'] += 1
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    resultados['errores'].append(f'Error en pagos: {str(e)}')
        
        # Registrar en auditoría
        try:
            log = AuditLog(
                usuario=current_user.username if current_user.is_authenticated else 'sistema',
                accion='restaurar_backup',
                entidad='sistema',
                detalle=f'Backup restaurado: {resultados["clientes_importados"]} clientes, {resultados["pagos_importados"]} pagos, {resultados["planes_importados"]} planes'
            )
            db.session.add(log)
            db.session.commit()
        except:
            pass
        
        return jsonify({
            'success': True,
            'mensaje': 'Backup restaurado exitosamente',
            'resultados': resultados
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== FICHA CLIENTE ==

@app.route('/ficha-cliente/<int:cliente_id>')
@login_required
def ficha_cliente(cliente_id):
    """Genera una ficha imprimible del cliente"""
    cliente = Cliente.query.get_or_404(cliente_id)
    pagos = Pago.query.filter_by(cliente_id=cliente_id).order_by(Pago.fecha_pago.desc()).limit(12).all()
    config = ConfigMikroTik.query.first()
    return render_template('ficha_cliente.html', cliente=cliente, pagos=pagos, config=config, now=datetime.now().strftime('%d/%m/%Y %H:%M'))


# Ejecutar migración al importar (para gunicorn)
init_db()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)

