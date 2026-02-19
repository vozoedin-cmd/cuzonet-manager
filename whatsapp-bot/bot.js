// ============================================
// CuzoNet WhatsApp Bot - Registro de Pagos
// ============================================
// Comandos disponibles en el grupo:
//   !pago Juan Perez 200
//   !pago 172.16.1.18 200
//   !pago Juan Perez 200 transferencia
//   !consulta Juan Perez
//   !consulta 172.16.1.18
//   !ayuda
// ============================================

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Detectar si estamos en servidor Linux
const IS_SERVER = os.platform() === 'linux';

// ============== CONFIGURACIÓN ==============
const CONFIG = {
    // URL de tu sistema CuzoNet (cambiar según tu servidor)
    // En servidor: localhost, en local: DigitalOcean
    API_URL: process.env.API_URL || (IS_SERVER ? 'http://127.0.0.1:5000' : 'https://rb-cuzonet-app-t5sph.ondigitalocean.app'),

    // ID del grupo de WhatsApp donde operará el bot (se muestra al iniciar)
    // Déjalo vacío '' para que funcione en TODOS los grupos/chats
    GRUPO_ID: '120363419809450940@g.us',

    // Prefijo de comandos
    PREFIJO: '!',

    // Métodos de pago válidos
    METODOS_PAGO: ['efectivo', 'transferencia', 'deposito', 'tarjeta'],
};

// ============== CLIENTE WHATSAPP ==============
const puppeteerArgs = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
];

// En servidor Linux, agregar flags de bajo consumo de memoria
if (IS_SERVER) {
    puppeteerArgs.push(
        '--disable-software-rasterizer',
        '--disable-extensions',
        '--disable-background-networking',
        '--disable-default-apps',
        '--disable-sync',
        '--no-first-run',
        '--single-process',
        '--no-zygote',
        '--js-flags=--max-old-space-size=256'
    );
}

const puppeteerConfig = {
    headless: true,
    args: puppeteerArgs,
};

// En servidor Linux, usar Chromium del sistema
if (IS_SERVER) {
    puppeteerConfig.executablePath = '/snap/bin/chromium';
}

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: './sesion_whatsapp' }),
    puppeteer: puppeteerConfig,
});

// ============== EVENTOS ==============
client.on('qr', (qr) => {
    console.log('\n📱 Escanea este código QR con WhatsApp:\n');
    qrcode.generate(qr, { small: true });
    console.log('\nAbre WhatsApp > Dispositivos vinculados > Vincular dispositivo\n');

    // En servidor, guardar QR como pagina web accesible
    if (IS_SERVER) {
        try {
            const staticDir = path.join(__dirname, '..', 'static');
            const qrDataPath = path.join(staticDir, 'qr_data.txt');
            fs.writeFileSync(qrDataPath, qr);
            console.log('📸 QR guardado en web: http://167.99.58.189/static/qr.html');
        } catch (err) {
            console.error('Error guardando QR:', err.message);
        }
    }
});

client.on('ready', async () => {
    console.log('✅ Bot de WhatsApp conectado correctamente!');
    console.log('📋 Esperando comandos...\n');

    // Mostrar los grupos disponibles para configurar
    const chats = await client.getChats();
    const grupos = chats.filter((c) => c.isGroup);
    if (grupos.length > 0) {
        console.log('📂 Grupos disponibles:');
        grupos.forEach((g) => {
            console.log(`   - "${g.name}" => ID: ${g.id._serialized}`);
        });
        console.log('\n💡 Copia el ID del grupo y pégalo en CONFIG.GRUPO_ID en bot.js\n');
    }
});

client.on('authenticated', () => {
    console.log('🔐 Sesión autenticada');
});

client.on('auth_failure', (msg) => {
    console.error('❌ Error de autenticación:', msg);
});

client.on('disconnected', (reason) => {
    console.log('⚠️ Bot desconectado:', reason);
    console.log('🔄 Intentando reconectar...');
    client.initialize();
});

// ============== MANEJO DE MENSAJES ==============
client.on('message_create', async (message) => {
    try {
        // Si se configuró un grupo específico, solo responder ahí
        const chatId = message.from;
        if (CONFIG.GRUPO_ID && chatId !== CONFIG.GRUPO_ID) return;

        const texto = message.body.trim();

        // Solo procesar mensajes que empiecen con el prefijo
        if (!texto.startsWith(CONFIG.PREFIJO)) return;

        const partes = texto.substring(1).trim().split(/\s+/);
        const comando = partes[0]?.toLowerCase();

        switch (comando) {
            case 'pago':
                await procesarPago(message, partes.slice(1));
                break;
            case 'cliente':
                await registrarCliente(message, partes.slice(1));
                break;
            case 'consulta':
                await consultarCliente(message, partes.slice(1));
                break;
            case 'ayuda':
            case 'help':
                await mostrarAyuda(message);
                break;
            default:
                await message.reply(
                    '❓ Comando no reconocido. Escribe *!ayuda* para ver los comandos disponibles.'
                );
        }
    } catch (error) {
        console.error('Error procesando mensaje:', error);
        await message.reply('❌ Error interno del bot. Intenta de nuevo.');
    }
});

// ============== FUNCIONES PRINCIPALES ==============

/**
 * Procesar comando de pago
 * Formatos aceptados:
 *   !pago Juan Perez 200
 *   !pago 172.16.1.18 200
 *   !pago Juan Perez 200 transferencia
 *   !pago Juan Perez 200 transferencia ref:12345
 */
async function procesarPago(message, args) {
    if (args.length < 2) {
        await message.reply(
            '⚠️ Formato incorrecto.\n\n' +
            '📝 *Uso:*\n' +
            '`!pago [nombre o IP] [monto]`\n' +
            '`!pago [nombre o IP] [monto] [método]`\n\n' +
            '📌 *Ejemplos:*\n' +
            '`!pago Juan Perez 200`\n' +
            '`!pago 172.16.1.18 200`\n' +
            '`!pago Juan Perez 200 transferencia`'
        );
        return;
    }

    // Extraer monto (buscar el número desde el final)
    let monto = null;
    let montoIndex = -1;
    let metodoPago = 'efectivo';
    let referencia = '';

    // Buscar monto y método de pago desde el final
    for (let i = args.length - 1; i >= 1; i--) {
        // Verificar si es referencia (ref:xxx)
        if (args[i].toLowerCase().startsWith('ref:')) {
            referencia = args[i].substring(4);
            continue;
        }
        // Verificar si es método de pago
        if (CONFIG.METODOS_PAGO.includes(args[i].toLowerCase())) {
            metodoPago = args[i].toLowerCase();
            continue;
        }
        // Verificar si es monto
        const num = parseFloat(args[i].replace('Q', '').replace('q', ''));
        if (!isNaN(num) && num > 0) {
            monto = num;
            montoIndex = i;
            break;
        }
    }

    if (!monto || montoIndex < 1) {
        await message.reply('⚠️ No pude identificar el monto. Asegúrate de escribir un número válido.\n\nEjemplo: `!pago Juan Perez 200`');
        return;
    }

    // Extraer identificador del cliente (todo antes del monto)
    const identificador = args.slice(0, montoIndex).join(' ');

    if (!identificador) {
        await message.reply('⚠️ Debes indicar el nombre o IP del cliente.\n\nEjemplo: `!pago Juan Perez 200`');
        return;
    }

    // Buscar cliente
    let cliente;
    try {
        cliente = await buscarCliente(identificador);
    } catch (error) {
        if (error.message === 'NO_CONEXION') {
            await message.reply('❌ No se pudo conectar con el sistema CuzoNet. Verifica que esté corriendo.');
        } else if (error.message === 'SIN_CLIENTES') {
            await message.reply('⚠️ No hay clientes registrados en el sistema.');
        } else {
            await message.reply('❌ Error al consultar la API del sistema.');
        }
        return;
    }

    if (!cliente) {
        await message.reply(
            `❌ No se encontró ningún cliente con: *${identificador}*\n\n` +
            '💡 Verifica el nombre o IP e intenta de nuevo.\n' +
            '💡 Prueba con la IP del cliente si el nombre no funciona.'
        );
        return;
    }

    // Si hay múltiples coincidencias
    if (Array.isArray(cliente) && cliente.length > 1) {
        let lista = '⚠️ Se encontraron varios clientes:\n\n';
        cliente.slice(0, 5).forEach((c, i) => {
            lista += `${i + 1}. *${c.nombre}* (${c.ip_address}) - Q${c.precio_mensual}\n`;
        });
        lista += '\n💡 Sé más específico con el nombre o usa la IP.';
        await message.reply(lista);
        return;
    }

    const clienteData = Array.isArray(cliente) ? cliente[0] : cliente;

    // Registrar el pago
    try {
        const respuesta = await axios.post(`${CONFIG.API_URL}/api/pago`, {
            cliente_id: clienteData.id,
            monto: monto,
            metodo_pago: metodoPago,
            referencia: referencia,
            notas: `Registrado via WhatsApp Bot`,
            registrado_por: 'whatsapp-bot',
        });

        if (respuesta.data.success) {
            const estadoEmoji = clienteData.estado === 'cortado' || clienteData.estado === 'suspendido'
                ? '\n🟢 *Cliente reactivado automáticamente*'
                : '';

            await message.reply(
                `✅ *PAGO REGISTRADO*\n\n` +
                `👤 *Cliente:* ${clienteData.nombre}\n` +
                `🌐 *IP:* ${clienteData.ip_address}\n` +
                `💰 *Monto:* Q${monto.toFixed(2)}\n` +
                `💳 *Método:* ${metodoPago}\n` +
                `📅 *Fecha:* ${new Date().toLocaleDateString('es-GT')}\n` +
                (referencia ? `🔖 *Ref:* ${referencia}\n` : '') +
                estadoEmoji
            );
            console.log(`✅ Pago Q${monto} registrado para ${clienteData.nombre} (${clienteData.ip_address})`);
        } else {
            await message.reply(`❌ Error al registrar: ${respuesta.data.error || 'Error desconocido'}`);
        }
    } catch (error) {
        console.error('Error registrando pago:', error.message);
        await message.reply('❌ No se pudo conectar con el sistema. Verifica que CuzoNet esté corriendo.');
    }
}

/**
 * Consultar información de un cliente
 * Formato: !consulta Juan Perez  o  !consulta 172.16.1.18
 */
async function consultarCliente(message, args) {
    if (args.length < 1) {
        await message.reply('⚠️ Uso: `!consulta [nombre o IP]`\n\nEjemplo: `!consulta Juan Perez`');
        return;
    }

    const identificador = args.join(' ');
    let cliente;
    try {
        cliente = await buscarCliente(identificador);
    } catch (error) {
        if (error.message === 'NO_CONEXION') {
            await message.reply('❌ No se pudo conectar con el sistema CuzoNet. Verifica que esté corriendo.');
        } else if (error.message === 'SIN_CLIENTES') {
            await message.reply('⚠️ No hay clientes registrados en el sistema.');
        } else {
            await message.reply('❌ Error al consultar la API del sistema.');
        }
        return;
    }

    if (!cliente) {
        await message.reply(`❌ No se encontró: *${identificador}*`);
        return;
    }

    if (Array.isArray(cliente) && cliente.length > 1) {
        let lista = '📋 *Clientes encontrados:*\n\n';
        cliente.slice(0, 10).forEach((c, i) => {
            const estadoEmoji = c.estado === 'activo' ? '🟢' : c.estado === 'cortado' ? '🔴' : '🟡';
            lista += `${i + 1}. ${estadoEmoji} *${c.nombre}* - ${c.ip_address} - Q${c.precio_mensual}\n`;
        });
        await message.reply(lista);
        return;
    }

    const c = Array.isArray(cliente) ? cliente[0] : cliente;
    const estadoEmoji = c.estado === 'activo' ? '🟢' : c.estado === 'cortado' ? '🔴' : '🟡';

    await message.reply(
        `📋 *INFORMACIÓN DEL CLIENTE*\n\n` +
        `👤 *Nombre:* ${c.nombre}\n` +
        `🌐 *IP:* ${c.ip_address}\n` +
        `📡 *Plan:* ${c.plan || 'N/A'}\n` +
        `${estadoEmoji} *Estado:* ${c.estado}\n` +
        `💰 *Precio:* Q${c.precio_mensual || 0}\n` +
        `📊 *Saldo pendiente:* Q${c.saldo_pendiente || 0}\n` +
        `📅 *Último pago:* ${c.fecha_ultimo_pago ? new Date(c.fecha_ultimo_pago).toLocaleDateString('es-GT') : 'Sin pagos'}\n` +
        `📆 *Próximo pago:* ${c.fecha_proximo_pago ? new Date(c.fecha_proximo_pago).toLocaleDateString('es-GT') : 'N/A'}\n` +
        `✂️ *Día de corte:* ${c.dia_corte}`
    );
}

/**
 * Registrar un nuevo cliente
 * Formato FLEXIBLE: !cliente nombre / IP / y los demás campos en CUALQUIER ORDEN
 * El bot detecta automáticamente qué es cada campo:
 *   - IP: formato xxx.xxx.xxx.xxx
 *   - Teléfono: 8 dígitos seguidos
 *   - Plan: contiene "mbps", "basico", "estandar", "premium", etc.
 *   - Precio: número >= 50 (ej: 200, 150)
 *   - Día de corte: número entre 1 y 28
 *   - Dirección: todo lo demás (texto con letras)
 */
async function registrarCliente(message, args) {
    // Unir todo y separar por /
    const textoCompleto = args.join(' ');
    const campos = textoCompleto.split('/').map(c => c.trim()).filter(c => c.length > 0);

    if (campos.length < 2) {
        await message.reply(
            '⚠️ *Formato incorrecto.*\n\n' +
            '📝 *Uso (separar con / ):*\n' +
            '`!cliente nombre / IP / y los demás datos`\n\n' +
            '🤖 *El bot detecta automáticamente:*\n' +
            '• Teléfono (8 dígitos)\n' +
            '• Plan (ej: Basico 7Mbps)\n' +
            '• Precio (número >= 50)\n' +
            '• Día de corte (número 1-28)\n' +
            '• Dirección (texto restante)\n\n' +
            '📌 *Ejemplo:*\n' +
            '`!cliente Juan Perez / 172.16.1.50 / 32472792 / Aldea Chinaha / 15 / 200`\n\n' +
            '📌 *Con plan:*\n' +
            '`!cliente Juan Perez / 172.16.1.50 / Basico 7Mbps / 32472792 / Aldea Chinaha / 15 / 200`\n\n' +
            '📌 *Mínimo (nombre + IP):*\n' +
            '`!cliente Juan Perez / 172.16.1.50`\n\n' +
            'ℹ️ No importa el orden después de nombre e IP.'
        );
        return;
    }

    // El primer campo SIEMPRE es el nombre
    const nombre = campos[0];

    // Detectar automáticamente cada campo restante
    let ip = '';
    let plan = 'Basico 7Mbps';
    let telefono = '';
    let direccion = '';
    let diaCorteFinal = 1;
    let precio = 0;
    let velocidadDown = '7M';
    let velocidadUp = '7M';

    const camposRestantes = campos.slice(1);
    const camposNoIdentificados = [];

    for (const campo of camposRestantes) {
        // Detectar IP (xxx.xxx.xxx.xxx)
        if (/^(\d{1,3}\.){3}\d{1,3}$/.test(campo)) {
            ip = campo;
        }
        // Detectar Plan (contiene mbps, basico, estandar, premium, etc.)
        else if (/mbps|básico|basico|estandar|estándar|premium|avanzado|mega/i.test(campo)) {
            plan = campo;
            // Extraer velocidad del plan si menciona Mbps
            const matchVel = campo.match(/(\d+)\s*mbps/i);
            if (matchVel) {
                velocidadDown = matchVel[1] + 'M';
                velocidadUp = matchVel[1] + 'M';
            }
        }
        // Detectar Teléfono (solo dígitos, 8 o más caracteres)
        else if (/^\d{8,}$/.test(campo.replace(/[-\s\+]/g, ''))) {
            telefono = campo;
        }
        // Detectar solo un número
        else if (/^\d+(\.\d+)?$/.test(campo)) {
            const num = parseFloat(campo);
            if (num >= 1 && num <= 28 && diaCorteFinal === 1 && precio === 0) {
                // Si es un número pequeño (1-28) y aún no tenemos día de corte
                // Lo guardamos temporalmente como posible día de corte
                // pero si viene otro número después, este podría ser precio
                if (num >= 50) {
                    // Probablemente es precio (50+)
                    precio = num;
                } else {
                    // Probablemente es día de corte (1-28)
                    diaCorteFinal = num;
                }
            } else if (num >= 50) {
                precio = num;
            } else if (num >= 1 && num <= 28 && diaCorteFinal === 1) {
                diaCorteFinal = num;
            }
        }
        // Todo lo demás es dirección
        else if (/[a-záéíóúñ]/i.test(campo)) {
            // Si tiene letras y no es plan ni nombre, es dirección
            if (direccion) {
                direccion += ', ' + campo;
            } else {
                direccion = campo;
            }
        }
    }

    // Validaciones
    if (!nombre) {
        await message.reply('⚠️ El *nombre* es obligatorio.');
        return;
    }

    if (!ip) {
        await message.reply(
            '⚠️ No detecté la *IP* del cliente.\n\n' +
            'Asegúrate de incluir la IP en formato: `172.16.1.50`\n\n' +
            'Ejemplo: `!cliente Juan Perez / 172.16.1.50 / 200`'
        );
        return;
    }

    // Mostrar resumen antes de registrar para que el usuario confirme visualmente
    console.log(`📝 Registrando/actualizando cliente: ${nombre} | IP: ${ip} | Plan: ${plan} | Tel: ${telefono} | Dir: ${direccion} | Corte: ${diaCorteFinal} | Precio: ${precio}`);

    // Primero verificar si la IP ya existe para decidir si crear o actualizar
    let clienteExistente = null;
    try {
        const resp = await axios.get(`${CONFIG.API_URL}/api/clientes`);
        if (resp.data.success && resp.data.clientes) {
            clienteExistente = resp.data.clientes.find(c => c.ip_address === ip);
        }
    } catch (e) {
        console.error('Error verificando cliente existente:', e.message);
    }

    try {
        if (clienteExistente) {
            // === ACTUALIZAR CLIENTE EXISTENTE ===
            const datosActualizar = {};
            // Siempre enviar nombre
            datosActualizar.nombre = nombre;
            // Enviar todos los campos que el usuario proporcionó
            if (telefono) datosActualizar.telefono = telefono;
            if (direccion) datosActualizar.direccion = direccion;
            // Siempre enviar plan, velocidades, precio y día de corte
            datosActualizar.plan = plan;
            datosActualizar.velocidad_download = velocidadDown;
            datosActualizar.velocidad_upload = velocidadUp;
            if (precio > 0) datosActualizar.precio_mensual = precio;
            datosActualizar.dia_corte = diaCorteFinal;

            const respuesta = await axios.put(`${CONFIG.API_URL}/api/cliente/${clienteExistente.id}`, datosActualizar);

            if (respuesta.data.success) {
                // Mostrar qué cambió
                const cambios = [];
                if (nombre !== clienteExistente.nombre) cambios.push(`👤 Nombre: ${clienteExistente.nombre} → *${nombre}*`);
                if (telefono && telefono !== (clienteExistente.telefono || '')) cambios.push(`📞 Teléfono: ${clienteExistente.telefono || 'N/A'} → *${telefono}*`);
                if (direccion && direccion !== (clienteExistente.direccion || '')) cambios.push(`📍 Dirección: ${clienteExistente.direccion || 'N/A'} → *${direccion}*`);
                if (plan !== 'Basico 7Mbps' && plan !== clienteExistente.plan) cambios.push(`📡 Plan: ${clienteExistente.plan} → *${plan}*`);
                if (precio > 0 && precio !== clienteExistente.precio_mensual) cambios.push(`💰 Precio: Q${clienteExistente.precio_mensual} → *Q${precio}*`);
                if (diaCorteFinal !== clienteExistente.dia_corte) cambios.push(`✂️ Día corte: ${clienteExistente.dia_corte} → *${diaCorteFinal}*`);

                const cambiosTexto = cambios.length > 0 
                    ? cambios.join('\n') 
                    : '_Sin cambios detectados_';

                await message.reply(
                    `🔄 *CLIENTE ACTUALIZADO*\n` +
                    `━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n` +
                    `👤 *${nombre}*\n` +
                    `🌐 *IP:* ${ip}\n\n` +
                    `📝 *Cambios:*\n${cambiosTexto}`
                );
                console.log(`🔄 Cliente actualizado: ${nombre} (${ip})`);
            } else {
                await message.reply(`❌ Error al actualizar: ${respuesta.data.error || 'Error desconocido'}`);
            }
        } else {
            // === CREAR CLIENTE NUEVO ===
            const respuesta = await axios.post(`${CONFIG.API_URL}/api/cliente`, {
                nombre: nombre,
                ip_address: ip,
                plan: plan,
                telefono: telefono,
                direccion: direccion,
                dia_corte: diaCorteFinal,
                precio_mensual: precio,
                velocidad_download: velocidadDown,
                velocidad_upload: velocidadUp,
            });

            if (respuesta.data.success) {
                await message.reply(
                    `✅ *CLIENTE REGISTRADO*\n` +
                    `━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n` +
                    `👤 *Nombre:* ${nombre}\n` +
                    `🌐 *IP:* ${ip}\n` +
                    `📡 *Plan:* ${plan}\n` +
                    `📞 *Teléfono:* ${telefono || 'N/A'}\n` +
                    `📍 *Dirección:* ${direccion || 'N/A'}\n` +
                    `✂️ *Día de corte:* ${diaCorteFinal}\n` +
                    `💰 *Precio:* Q${precio.toFixed(2)}`
                );
                console.log(`✅ Cliente registrado: ${nombre} (${ip})`);
            } else {
                await message.reply(`❌ Error: ${respuesta.data.error || 'No se pudo registrar'}`);
            }
        }
    } catch (error) {
        if (error.response && error.response.data) {
            await message.reply(`❌ ${error.response.data.error || 'Error al procesar cliente'}`);
        } else {
            console.error('Error procesando cliente:', error.message);
            await message.reply('❌ No se pudo conectar con el sistema.');
        }
    }
}

/**
 * Mostrar ayuda
 */
async function mostrarAyuda(message) {
    await message.reply(
        `╔══════════════════════════╗\n` +
        `║  🌐 *CuzoNet Bot* 🤖     ║\n` +
        `║  _Panel de Comandos_     ║\n` +
        `╚══════════════════════════╝\n\n` +

        `💵 *REGISTRAR PAGO*\n` +
        `━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
        `▸ \`!pago [nombre] [monto]\`\n` +
        `▸ \`!pago [IP] [monto]\`\n` +
        `▸ \`!pago [nombre] [monto] [método]\`\n\n` +

        `👤 *REGISTRAR CLIENTE*\n` +
        `━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
        `▸ \`!cliente nombre / IP / datos...\`\n` +
        `🤖 _Detecta automáticamente: tel, plan, precio, dirección, día de corte_\n\n` +

        `🔍 *CONSULTAR CLIENTE*\n` +
        `━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
        `▸ \`!consulta [nombre o IP]\`\n\n` +

        `══════════════════════════\n` +
        `📌 *EJEMPLOS*\n` +
        `══════════════════════════\n\n` +
        `💵 Pago simple:\n` +
        `\`!pago Juan Perez 200\`\n\n` +
        `💳 Pago con método:\n` +
        `\`!pago 172.16.1.18 150 transferencia\`\n\n` +
        `👤 Cliente completo:\n` +
        `\`!cliente Juan Perez / 172.16.1.50 / 32472792 / Aldea Chinaha / 15 / 200\`\n\n` +
        `👤 Con plan:\n` +
        `\`!cliente Juan Perez / 172.16.1.50 / Basico 7Mbps / 32472792 / Aldea Chinaha / 15 / 200\`\n\n` +
        `👤 Cliente mínimo:\n` +
        `\`!cliente Juan Perez / 172.16.1.50\`\n\n` +
        `🔍 Consulta:\n` +
        `\`!consulta Adan Choc\`\n\n` +

        `💳 *Métodos de pago:* efectivo, transferencia, deposito, tarjeta\n\n` +
        `ℹ️ _Separa los campos del cliente con  /  (barra)_`
    );
}

// ============== FUNCIONES AUXILIARES ==============

/**
 * Buscar cliente por nombre o IP en el sistema
 * Retorna: cliente, array de clientes, null (no encontrado), o lanza error si la API falla
 */
async function buscarCliente(identificador) {
    // Obtener todos los clientes desde la API
    let respuesta;
    try {
        respuesta = await axios.get(`${CONFIG.API_URL}/api/clientes`);
    } catch (error) {
        console.error('Error conectando con la API:', error.message);
        throw new Error('NO_CONEXION');
    }

    if (!respuesta.data || !respuesta.data.success) {
        console.error('API respondió sin éxito:', JSON.stringify(respuesta.data));
        throw new Error('API_ERROR');
    }

    const clientes = respuesta.data.clientes;
    console.log(`📊 Total clientes en sistema: ${clientes.length}`);

    if (!clientes || clientes.length === 0) {
        throw new Error('SIN_CLIENTES');
    }

    // Verificar si es una IP
    const esIP = /^(\d{1,3}\.){3}\d{1,3}$/.test(identificador);

    if (esIP) {
        // Buscar por IP exacta
        const cliente = clientes.find((c) => c.ip_address === identificador);
        return cliente || null;
    }

    // Buscar por nombre (coincidencia parcial, sin importar mayúsculas/tildes)
    const busqueda = normalizarTexto(identificador);
    console.log(`🔍 Buscando: "${busqueda}"`);

    // Primero buscar coincidencia exacta
    const exacta = clientes.find((c) => normalizarTexto(c.nombre) === busqueda);
    if (exacta) return exacta;

    // Luego buscar coincidencia parcial
    const coincidencias = clientes.filter((c) => {
        const nombre = normalizarTexto(c.nombre);
        return nombre.includes(busqueda) || busqueda.includes(nombre);
    });

    // Si no hay coincidencias parciales, buscar por palabras individuales
    if (coincidencias.length === 0) {
        const palabras = busqueda.split(/\s+/);
        const porPalabras = clientes.filter((c) => {
            const nombre = normalizarTexto(c.nombre);
            return palabras.every((p) => nombre.includes(p));
        });
        if (porPalabras.length === 1) return porPalabras[0];
        if (porPalabras.length > 1) return porPalabras;
    }

    if (coincidencias.length === 0) return null;
    if (coincidencias.length === 1) return coincidencias[0];
    return coincidencias; // Múltiples coincidencias
}

/**
 * Normalizar texto para búsqueda (quitar tildes, minúsculas)
 */
function normalizarTexto(texto) {
    return texto
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim();
}

// ============== INICIAR BOT ==============
console.log('🚀 Iniciando CuzoNet WhatsApp Bot...');
console.log(`📡 Servidor API: ${CONFIG.API_URL}`);
console.log('⏳ Generando código QR...\n');

client.initialize();
