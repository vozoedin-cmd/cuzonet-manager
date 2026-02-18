# CuzoNet Manager - Sistema de Gestión de Clientes MikroTik

Sistema web para registrar clientes de internet y crear **Simple Queues** automáticamente en routers MikroTik vía API REST.

![Dashboard Preview](https://via.placeholder.com/800x400?text=CuzoNet+Manager+Dashboard)

## 🚀 Características

- ✅ **Registro de clientes** con datos completos
- ✅ **Creación automática de Simple Queues** en MikroTik
- ✅ **Suspender/Activar clientes** (habilita/deshabilita queues)
- ✅ **Dashboard en tiempo real** con estadísticas
- ✅ **Interfaz moderna y responsiva** (tema oscuro)
- ✅ **Gestión de planes de internet** predefinidos
- ✅ **API REST** para integraciones
- ✅ **Base de datos** SQLite (desarrollo) / PostgreSQL (producción)

## 📋 Requisitos

- Python 3.9+
- Router MikroTik con RouterOS 7.x (REST API habilitada)
- Digital Ocean cuenta (para producción)

## 🛠️ Instalación Local

1. **Clonar o descargar el proyecto**

2. **Crear entorno virtual:**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno:**
```bash
copy .env.example .env
# Editar .env con tus valores
```

5. **Ejecutar la aplicación:**
```bash
python app.py
```

6. **Abrir en el navegador:** http://localhost:5000

## 🌐 Despliegue en Digital Ocean

### Opción 1: App Platform (Recomendado)

1. **Subir código a GitHub**

2. **Crear App en Digital Ocean App Platform:**
   - Ir a [Digital Ocean Apps](https://cloud.digitalocean.com/apps)
   - Click "Create App"
   - Conectar con tu repositorio GitHub
   - Seleccionar rama `main`

3. **Configurar el servicio:**
   - Tipo: Web Service
   - Detectará automáticamente que es Python
   - Run Command: `gunicorn app:app --bind 0.0.0.0:$PORT`

4. **Agregar base de datos PostgreSQL:**
   - En "Add Resource" → "Database" → "Dev Database"
   - Digital Ocean conectará automáticamente la variable `DATABASE_URL`

5. **Configurar variables de entorno:**
   ```
   SECRET_KEY=tu-clave-secreta-muy-segura
   FLASK_ENV=production
   ```

6. **Deploy!** Tu app estará disponible en: `https://tu-app.ondigitalocean.app`

### Opción 2: Droplet

1. **Crear Droplet Ubuntu 22.04**

2. **Conectar por SSH y ejecutar:**
```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python y dependencias
sudo apt install python3-pip python3-venv nginx -y

# Clonar proyecto
git clone https://github.com/tu-usuario/cuzonet-manager.git
cd cuzonet-manager

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar .env
cp .env.example .env
nano .env  # Editar con tus valores

# Ejecutar con gunicorn
gunicorn app:app --bind 0.0.0.0:8000 --daemon

# Configurar Nginx como proxy reverso
sudo nano /etc/nginx/sites-available/cuzonet
```

3. **Configuración Nginx:**
```nginx
server {
    listen 80;
    server_name tu-ip-o-dominio;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

4. **Activar sitio:**
```bash
sudo ln -s /etc/nginx/sites-available/cuzonet /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## ⚙️ Configuración de MikroTik

Para que la aplicación pueda comunicarse con tu router MikroTik, necesitas habilitar la REST API:

### 1. Habilitar servicio www (REST API)

```routeros
/ip/service
set www port=80 disabled=no
# O para HTTPS:
set www-ssl port=443 disabled=no
```

### 2. Crear usuario con permisos de API

```routeros
/user
add name=api_user password=TuPasswordSeguro group=full
```

### 3. Permitir acceso en firewall (si es necesario)

```routeros
/ip/firewall/filter
add chain=input protocol=tcp dst-port=80 action=accept comment="REST API"
```

### 4. Configurar en la aplicación web

1. Ir a **Configuración** en la web
2. Ingresar:
   - **Host:** IP pública del router o dominio DDNS
   - **Puerto:** 80 (o 443 para HTTPS)
   - **Usuario:** api_user
   - **Contraseña:** TuPasswordSeguro
3. Click **"Probar Conexión"**
4. **Guardar**

## 📡 API REST

### Endpoints disponibles:

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/clientes` | Listar todos los clientes |
| POST | `/api/cliente` | Crear nuevo cliente |
| PUT | `/api/cliente/<id>` | Actualizar cliente |
| DELETE | `/api/cliente/<id>` | Eliminar cliente |
| POST | `/api/cliente/<id>/suspender` | Suspender cliente |
| POST | `/api/cliente/<id>/activar` | Activar cliente |
| GET | `/api/planes` | Listar planes |
| POST | `/api/plan` | Crear plan |
| GET | `/api/sync/queues` | Obtener queues de MikroTik |

### Ejemplo: Crear cliente

```bash
curl -X POST http://localhost:5000/api/cliente \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Juan Pérez",
    "ip_address": "192.168.1.100",
    "plan": "Premium 20Mbps",
    "velocidad_download": "20M",
    "velocidad_upload": "10M",
    "telefono": "+1234567890"
  }'
```

## 🔧 Estructura del Proyecto

```
PROYECTO 1/
├── app.py                 # Backend Flask principal
├── requirements.txt       # Dependencias Python
├── Procfile              # Configuración para Digital Ocean
├── runtime.txt           # Versión de Python
├── .env.example          # Plantilla de variables de entorno
├── templates/            # Plantillas HTML
│   ├── index.html        # Dashboard principal
│   ├── clientes.html     # Gestión de clientes
│   └── configuracion.html # Configuración MikroTik
└── static/
    ├── css/
    │   └── style.css     # Estilos modernos
    └── js/
        └── app.js        # Lógica frontend
```

## 🎨 Capturas de Pantalla

### Dashboard
- Estadísticas en tiempo real
- Lista de clientes recientes
- Acciones rápidas

### Registro de Cliente
- Formulario moderno
- Validación de IP
- Selección de plan con velocidades automáticas

### Configuración
- Conexión a MikroTik
- Gestión de planes
- Prueba de conexión

## 📝 Notas Importantes

1. **Seguridad:** En producción, usa HTTPS y cambia la SECRET_KEY
2. **Firewall:** Asegúrate de que el puerto de la REST API esté accesible
3. **IP Pública:** El router MikroTik necesita IP pública o DNS dinámico para acceso remoto
4. **Respaldos:** Configura respaldos automáticos de la base de datos

## 🤝 Soporte

Para soporte técnico o personalizaciones, contactar a:
- Email: soporte@cuzonet.com
- WhatsApp: +XXX XXXX XXXX

## 📜 Licencia

MIT License - Libre para uso comercial y personal.

---

Desarrollado con ❤️ por CuzoNet
