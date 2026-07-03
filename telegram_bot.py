import os
import telebot
from datetime import datetime
from dotenv import load_dotenv

# Importar la app de Flask y la base de datos de Cuzonet Manager
from app import app, db, Cliente, Pago

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID') # ID del usuario permitido

if not TOKEN:
    print("Error: No se encontró TELEGRAM_BOT_TOKEN en el archivo .env")
    exit(1)

bot = telebot.TeleBot(TOKEN)

def is_admin(message):
    if not ADMIN_ID:
        return True # Si no hay ADMIN_ID, permite a cualquiera (no recomendado)
    return str(message.from_user.id) == str(ADMIN_ID)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_admin(message):
        bot.reply_to(message, "⛔ No tienes permiso para usar este bot.")
        return
        
    bot.reply_to(message, 
        "🤖 *Bienvenido al Bot de Cuzonet Manager*\n\n"
        "Tengo acceso directo a tu base de datos ISP. Comandos disponibles:\n\n"
        "🔴 /morosos - Lista de clientes con fecha de pago vencida\n"
        "🔍 /buscar [nombre] - Busca información detallada de un cliente\n"
        "📊 /resumen - Muestra ingresos proyectados y clientes activos\n\n"
        "_Tip: Escribe los comandos en cualquier momento._",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['morosos'])
def command_morosos(message):
    if not is_admin(message):
        return
        
    bot.reply_to(message, "⏳ Consultando base de datos, por favor espera...")
    
    with app.app_context():
        # Clientes con fecha_proximo_pago vencida y estado activo
        hoy = datetime.now()
        morosos = Cliente.query.filter(
            Cliente.estado == 'activo',
            Cliente.fecha_proximo_pago < hoy
        ).all()
        
        if not morosos:
            bot.reply_to(message, "✅ ¡Felicidades! No tienes clientes activos en mora.")
            return
            
        texto = f"🔴 *CLIENTES MOROSOS ({len(morosos)})*\n\n"
        deuda_total = 0
        
        for c in morosos:
            # Calcular meses atrasados
            a_cobro, m_cobro = hoy.year, hoy.month
            a_prox, m_prox = c.fecha_proximo_pago.year, c.fecha_proximo_pago.month
            meses_atrasados = (a_cobro - a_prox) * 12 + (m_cobro - m_prox)
            if meses_atrasados <= 0:
                meses_atrasados = 1 # Por lo menos debe el mes que ya venció
                
            deuda = (c.saldo_pendiente or 0) + (meses_atrasados * (c.precio_mensual or 0))
            deuda_total += deuda
            
            texto += f"👤 *{c.nombre}*\n"
            texto += f"📅 Venció: {c.fecha_proximo_pago.strftime('%d/%m/%Y')}\n"
            texto += f"💰 Deuda aprox: Q{deuda:.2f}\n"
            texto += f"☎️ Tel: {c.telefono or 'N/A'}\n"
            texto += "-" * 20 + "\n"
            
        texto += f"\n💵 *DEUDA TOTAL ESTIMADA: Q{deuda_total:.2f}*"
        
        if len(texto) > 4000:
            bot.reply_to(message, texto[:4000])
            bot.reply_to(message, texto[4000:8000])
        else:
            bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['resumen'])
def command_resumen(message):
    if not is_admin(message):
        return
        
    with app.app_context():
        total_clientes = Cliente.query.count()
        activos = Cliente.query.filter_by(estado='activo').count()
        suspendidos = Cliente.query.filter_by(estado='suspendido').count()
        cortados = Cliente.query.filter_by(estado='cortado').count()
        
        # Ingreso proyectado mensual
        clientes_activos = Cliente.query.filter_by(estado='activo').all()
        ingreso_mensual = sum(c.precio_mensual or 0 for c in clientes_activos)
        
        texto = (
            "📊 *RESUMEN DE RED CUZONET*\n\n"
            f"👥 *Total Registrados:* {total_clientes}\n"
            f"✅ *Activos:* {activos}\n"
            f"⏸️ *Suspendidos:* {suspendidos}\n"
            f"✂️ *Cortados:* {cortados}\n\n"
            f"💵 *Ingreso Mensual Proyectado:* Q{ingreso_mensual:.2f}"
        )
        bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['buscar'])
def command_buscar(message):
    if not is_admin(message):
        return
        
    try:
        nombre_buscar = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "⚠️ Uso correcto: `/buscar Nombre del Cliente`", parse_mode="Markdown")
        return
        
    with app.app_context():
        clientes = Cliente.query.filter(Cliente.nombre.ilike(f'%{nombre_buscar}%')).all()
        
        if not clientes:
            bot.reply_to(message, f"❌ No se encontró ningún cliente con el nombre '{nombre_buscar}'.")
            return
            
        texto = f"🔍 *Resultados para '{nombre_buscar}':*\n\n"
        for c in clientes[:5]: # Mostrar máximo 5
            texto += f"👤 *{c.nombre}*\n"
            texto += f"📡 IP: `{c.ip_address}`\n"
            texto += f"📦 Plan: {c.plan}\n"
            texto += f"📊 Estado: {c.estado.upper()}\n"
            texto += f"💵 Cuota: Q{c.precio_mensual or 0}\n"
            
            if c.fecha_proximo_pago:
                hoy = datetime.now()
                vencido = "⚠️ VENCIDO" if c.fecha_proximo_pago < hoy else "✅ Al día"
                texto += f"📅 Próximo pago: {c.fecha_proximo_pago.strftime('%d/%m/%Y')} ({vencido})\n"
            texto += "-" * 20 + "\n"
            
        if len(clientes) > 5:
            texto += f"\n_... y {len(clientes) - 5} resultados más._"
            
        bot.reply_to(message, texto, parse_mode="Markdown")

if __name__ == '__main__':
    print("========================================")
    print("🤖 Iniciando Bot de Telegram Cuzonet...")
    print("========================================")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"Error crítico en el bot: {e}")
