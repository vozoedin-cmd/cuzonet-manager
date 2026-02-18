# CuzoNet WhatsApp Bot 🤖

Bot de WhatsApp para registrar pagos automáticamente en CuzoNet Manager.

## Requisitos

- **Node.js** v18 o superior ([descargar](https://nodejs.org/))
- **CuzoNet Manager** corriendo (tu app Flask)
- **Google Chrome** instalado (el bot lo usa internamente)

## Instalación

```bash
cd whatsapp-bot
npm install
```

## Uso

1. **Asegúrate que CuzoNet esté corriendo** en `http://127.0.0.1:5000`

2. **Inicia el bot:**
   ```bash
   npm start
   ```

3. **Escanea el código QR** que aparece en la terminal con tu WhatsApp:
   - Abre WhatsApp > ⋮ > Dispositivos vinculados > Vincular dispositivo

4. **Configura el grupo** (opcional):
   - Al iniciar, el bot muestra los IDs de tus grupos
   - Copia el ID del grupo deseado y pégalo en `CONFIG.GRUPO_ID` en `bot.js`
   - Si lo dejas vacío, funciona en todos los chats

## Comandos

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `!pago [nombre] [monto]` | Registrar pago por nombre | `!pago Juan Perez 200` |
| `!pago [IP] [monto]` | Registrar pago por IP | `!pago 172.16.1.18 200` |
| `!pago [nombre] [monto] [método]` | Pago con método específico | `!pago Juan Perez 200 transferencia` |
| `!pago [nombre] [monto] [método] ref:XXX` | Pago con referencia | `!pago Juan 200 deposito ref:12345` |
| `!consulta [nombre o IP]` | Ver info del cliente | `!consulta Adan Choc` |
| `!ayuda` | Ver comandos disponibles | `!ayuda` |

### Métodos de pago

- `efectivo` (por defecto)
- `transferencia`
- `deposito`
- `tarjeta`

## Configuración

Edita las variables en `bot.js`:

```javascript
const CONFIG = {
    API_URL: 'http://127.0.0.1:5000',  // URL de tu CuzoNet
    GRUPO_ID: '',                        // ID del grupo (vacío = todos)
    PREFIJO: '!',                        // Prefijo de comandos
};
```

## Notas

- La sesión de WhatsApp se guarda en `./sesion_whatsapp/` para no escanear QR cada vez
- Si cambias de número, elimina la carpeta `sesion_whatsapp/` y escanea de nuevo
- Los pagos registrados aparecen con `registrado_por: whatsapp-bot` en el sistema
- El bot busca clientes por coincidencia parcial de nombre (sin importar mayúsculas o tildes)
