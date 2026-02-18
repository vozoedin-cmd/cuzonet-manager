/**
 * CuzoNet Manager - Frontend JavaScript
 * Manejo de clientes y comunicación con MikroTik
 */

// ============== TEMA OSCURO/CLARO ==============

function toggleTheme() {
    const isLight = document.body.classList.toggle('light-mode');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
    const icon = document.getElementById('themeIcon');
    const text = document.getElementById('themeText');
    if (icon) icon.className = isLight ? 'fas fa-sun' : 'fas fa-moon';
    if (text) text.textContent = isLight ? 'Modo Oscuro' : 'Modo Claro';
}

// Cargar tema guardado al iniciar
(function() {
    if (localStorage.getItem('theme') === 'light') {
        document.body.classList.add('light-mode');
        document.addEventListener('DOMContentLoaded', function() {
            const icon = document.getElementById('themeIcon');
            const text = document.getElementById('themeText');
            if (icon) icon.className = 'fas fa-sun';
            if (text) text.textContent = 'Modo Oscuro';
        });
    }
})();

// ============== UTILIDADES ==============

/**
 * Mostrar notificación toast
 */
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'check-circle';
    if (type === 'error') icon = 'times-circle';
    if (type === 'warning') icon = 'exclamation-triangle';

    toast.innerHTML = `
        <i class="fas fa-${icon} toast-icon"></i>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;

    container.appendChild(toast);

    // Eliminar después de 5 segundos
    setTimeout(() => {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

/**
 * Abrir modal
 */
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

/**
 * Cerrar modal
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Cerrar modal al hacer clic fuera
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// Cerrar modal con Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    }
});

// ============== CLIENTES ==============

/**
 * Formulario de nuevo cliente
 */
const clienteForm = document.getElementById('clienteForm');
if (clienteForm) {
    clienteForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        const planSelect = document.getElementById('plan');
        const selectedOption = planSelect.options[planSelect.selectedIndex];

        const formData = {
            nombre: document.getElementById('nombre').value,
            ip_address: document.getElementById('ip_address').value,
            plan_id: planSelect.value,
            plan: selectedOption.dataset.name || selectedOption.text.split('(')[0].trim(),
            telefono: document.getElementById('telefono').value,
            email: document.getElementById('email').value,
            cedula: document.getElementById('cedula').value,
            direccion: document.getElementById('direccion').value,
            dia_corte: document.getElementById('dia_corte').value || 1,
            precio_mensual: document.getElementById('precio_mensual').value || selectedOption.dataset.precio || 0,
            velocidad_download: document.getElementById('velocidad_download').value || selectedOption.dataset.download,
            velocidad_upload: document.getElementById('velocidad_upload').value || selectedOption.dataset.upload
        };

        try {
            const response = await fetch('/api/cliente', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const result = await response.json();

            if (result.success) {
                showToast('Cliente registrado exitosamente', 'success');
                closeModal('clienteModal');

                // Recargar página después de un breve delay
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast(result.error || 'Error al registrar cliente', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            showToast('Error de conexión', 'error');
        }
    });
}

/**
 * Actualizar velocidades al cambiar plan
 */
function updatePlanSpeeds() {
    const planSelect = document.getElementById('plan');
    const selectedOption = planSelect.options[planSelect.selectedIndex];

    const downloadInput = document.getElementById('velocidad_download');
    const uploadInput = document.getElementById('velocidad_upload');
    const precioInput = document.getElementById('precio_mensual');

    if (downloadInput && uploadInput) {
        downloadInput.placeholder = selectedOption.dataset.download || '10M';
        uploadInput.placeholder = selectedOption.dataset.upload || '5M';
    }

    if (precioInput && selectedOption.dataset.precio) {
        precioInput.value = selectedOption.dataset.precio;
    }
}

/**
 * Suspender cliente
 */
async function suspenderCliente(id) {
    if (!confirm('¿Está seguro de suspender este cliente? El queue en MikroTik será deshabilitado.')) {
        return;
    }

    try {
        const response = await fetch(`/api/cliente/${id}/suspender`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showToast('Cliente suspendido', 'success');
            setTimeout(() => location.reload(), 500);
        } else {
            showToast(result.error || 'Error al suspender', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error de conexión', 'error');
    }
}

/**
 * Activar cliente
 */
async function activarCliente(id) {
    try {
        const response = await fetch(`/api/cliente/${id}/activar`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showToast('Cliente activado', 'success');
            setTimeout(() => location.reload(), 500);
        } else {
            showToast(result.error || 'Error al activar', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error de conexión', 'error');
    }
}

/**
 * Eliminar cliente
 */
/**
 * Ordenar tabla de clientes por columna
 */
let currentSort = { column: '', direction: 'asc' };

function sortTable(column) {
    const table = document.getElementById('clientesTable');
    if (!table) return;

    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    // Determinar dirección
    if (currentSort.column === column) {
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort.column = column;
        currentSort.direction = 'asc';
    }

    // Actualizar iconos
    table.querySelectorAll('th.sortable').forEach(th => {
        th.classList.remove('asc', 'desc');
        th.querySelector('i').className = 'fas fa-sort';
    });

    const activeHeader = table.querySelector(`th[data-sort="${column}"]`);
    if (activeHeader) {
        activeHeader.classList.add(currentSort.direction);
        activeHeader.querySelector('i').className = currentSort.direction === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
    }

    // Ordenar filas
    rows.sort((a, b) => {
        let valA = (a.dataset[column] || '').toLowerCase();
        let valB = (b.dataset[column] || '').toLowerCase();

        // Para IP, ordenar numéricamente
        if (column === 'ip') {
            const ipToNum = ip => ip.split('.').reduce((acc, octet) => acc * 256 + parseInt(octet || 0), 0);
            valA = ipToNum(valA);
            valB = ipToNum(valB);
            return currentSort.direction === 'asc' ? valA - valB : valB - valA;
        }

        // Ordenar texto
        if (valA < valB) return currentSort.direction === 'asc' ? -1 : 1;
        if (valA > valB) return currentSort.direction === 'asc' ? 1 : -1;
        return 0;
    });

    // Re-insertar filas ordenadas
    rows.forEach(row => tbody.appendChild(row));
}

/**
 * Enviar recordatorio por WhatsApp
 */
function enviarWhatsApp(telefono, nombre, precio, plan) {
    // Limpiar número de teléfono (quitar espacios, guiones, etc.)
    let numero = telefono.replace(/[\s\-\(\)\.]/g, '');
    // Si no empieza con código de país, agregar Guatemala (502)
    if (!numero.startsWith('+') && !numero.startsWith('502')) {
        numero = '502' + numero;
    }
    numero = numero.replace('+', '');
    
    const meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    const mesActual = meses[new Date().getMonth()];
    const anio = new Date().getFullYear();
    
    const mensaje = `Hola *${nombre}*, le saluda CuzoNet. 🌐\n\n` +
        `Le recordamos que su pago del servicio de internet correspondiente al mes de *${mesActual} ${anio}* se encuentra pendiente.\n\n` +
        `📋 *Detalle:*\n` +
        `• Plan: ${plan}\n` +
        `• Monto: Q${parseFloat(precio).toFixed(2)}\n\n` +
        `Por favor realizar su pago a la brevedad para evitar la suspensión del servicio.\n\n` +
        `¡Gracias por su preferencia! 🙏`;
    
    const url = `https://wa.me/${numero}?text=${encodeURIComponent(mensaje)}`;
    window.open(url, '_blank');
}

/**
 * Generar aviso de cobro individual para un cliente
 */
function generarAvisoIndividual(clienteId) {
    const mes = new Date().toISOString().slice(0, 7); // YYYY-MM
    window.open(`/aviso-cobro/cliente/${clienteId}/${mes}`, '_blank');
}

async function eliminarCliente(id, nombre) {
    if (!confirm(`¿Eliminar al cliente "${nombre}"?\n\nEsto también eliminará el queue de MikroTik.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/cliente/${id}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showToast('Cliente eliminado', 'success');
            setTimeout(() => location.reload(), 500);
        } else {
            showToast(result.error || 'Error al eliminar', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error de conexión', 'error');
    }
}

/**
 * Ver detalles de cliente
 */
async function viewCliente(id) {
    try {
        // Cargar datos del cliente y sus pagos en paralelo
        const [clienteRes, pagosRes] = await Promise.all([
            fetch('/api/clientes'),
            fetch(`/api/pagos/cliente/${id}`)
        ]);
        const result = await clienteRes.json();
        const pagosResult = await pagosRes.json();

        if (result.success) {
            const cliente = result.clientes.find(c => c.id === id);

            if (cliente) {
                const pagos = pagosResult.success ? pagosResult.pagos : [];
                
                let pagosHTML = '';
                if (pagos.length > 0) {
                    pagosHTML = `
                        <div class="detail-item full" style="margin-top: 16px;">
                            <span class="detail-label"><i class="fas fa-history"></i> Historial de Pagos (${pagos.length})</span>
                            <div style="max-height: 200px; overflow-y: auto; margin-top: 8px;">
                                <table style="width: 100%; font-size: 0.8rem; border-collapse: collapse;">
                                    <thead>
                                        <tr style="border-bottom: 1px solid rgba(14,165,233,0.2);">
                                            <th style="text-align: left; padding: 6px 8px; color: var(--text-secondary);">Fecha</th>
                                            <th style="text-align: left; padding: 6px 8px; color: var(--text-secondary);">Mes</th>
                                            <th style="text-align: right; padding: 6px 8px; color: var(--text-secondary);">Monto</th>
                                            <th style="text-align: left; padding: 6px 8px; color: var(--text-secondary);">Método</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${pagos.map(p => `
                                            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                                                <td style="padding: 6px 8px;">${p.fecha_pago ? p.fecha_pago.split(' ')[0] : '-'}</td>
                                                <td style="padding: 6px 8px;"><span class="badge">${p.mes_correspondiente || '-'}</span></td>
                                                <td style="padding: 6px 8px; text-align: right; color: #10b981; font-weight: 600;">Q${parseFloat(p.monto).toFixed(2)}</td>
                                                <td style="padding: 6px 8px;">${p.metodo_pago || '-'}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    `;
                } else {
                    pagosHTML = `
                        <div class="detail-item full" style="margin-top: 16px;">
                            <span class="detail-label"><i class="fas fa-history"></i> Historial de Pagos</span>
                            <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 8px;">
                                <i class="fas fa-info-circle"></i> No hay pagos registrados
                            </p>
                        </div>
                    `;
                }

                const detailsDiv = document.getElementById('clienteDetails');
                detailsDiv.innerHTML = `
                    <div class="client-detail-card">
                        <div class="detail-header">
                            <div class="client-avatar large ${cliente.estado === 'suspendido' ? 'suspended' : ''}">
                                ${cliente.nombre.charAt(0).toUpperCase()}
                            </div>
                            <div class="detail-name">
                                <h3>${cliente.nombre}</h3>
                                <span class="status-badge ${cliente.estado === 'activo' ? 'active' : 'suspended'}">
                                    <i class="fas fa-circle"></i> ${cliente.estado === 'activo' ? 'Activo' : cliente.estado === 'cortado' ? 'Cortado' : 'Suspendido'}
                                </span>
                            </div>
                        </div>
                        
                        <div class="detail-grid">
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-network-wired"></i> IP Address</span>
                                <code class="ip-badge">${cliente.ip_address}</code>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-box"></i> Plan</span>
                                <span>${cliente.plan}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-tachometer-alt"></i> Velocidad</span>
                                <span class="speed-badge">
                                    <i class="fas fa-arrow-down"></i> ${cliente.velocidad_download}
                                    <i class="fas fa-arrow-up"></i> ${cliente.velocidad_upload}
                                </span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-phone"></i> Teléfono</span>
                                <span>${cliente.telefono || 'No registrado'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-dollar-sign"></i> Precio Mensual</span>
                                <span style="color: #10b981; font-weight: 600;">Q${parseFloat(cliente.precio_mensual || 0).toFixed(2)}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-calendar-check"></i> Último Pago</span>
                                <span>${cliente.fecha_ultimo_pago || 'Sin pagos'}</span>
                            </div>
                            <div class="detail-item full">
                                <span class="detail-label"><i class="fas fa-map-marker-alt"></i> Dirección</span>
                                <span>${cliente.direccion || 'No registrada'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-server"></i> Queue MikroTik</span>
                                <span>${cliente.queue_name || 'N/A'}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-label"><i class="fas fa-calendar"></i> Registro</span>
                                <span>${cliente.fecha_registro || 'N/A'}</span>
                            </div>
                            ${pagosHTML}
                        </div>
                    </div>
                `;

                openModal('viewClienteModal');
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error al cargar detalles', 'error');
    }
}

// ============== TABLA Y FILTROS ==============

/**
 * Filtrar tabla de clientes
 */
function filterTable() {
    const searchInput = document.getElementById('searchInput');
    const filterEstado = document.getElementById('filterEstado');
    const filterPlan = document.getElementById('filterPlan');

    const searchValue = searchInput ? searchInput.value.toLowerCase() : '';
    const estadoValue = filterEstado ? filterEstado.value : '';
    const planValue = filterPlan ? filterPlan.value : '';

    const table = document.getElementById('clientesTable');
    if (!table) return;

    const rows = table.querySelectorAll('tbody tr[data-id]');

    rows.forEach(row => {
        const nombre = row.dataset.nombre ? row.dataset.nombre.toLowerCase() : '';
        const estado = row.dataset.estado || '';
        const plan = row.dataset.plan || '';
        const ip = row.querySelector('code') ? row.querySelector('code').textContent.toLowerCase() : '';

        const matchSearch = !searchValue ||
            nombre.includes(searchValue) ||
            ip.includes(searchValue) ||
            plan.toLowerCase().includes(searchValue);

        const matchEstado = !estadoValue || estado === estadoValue;
        const matchPlan = !planValue || plan === planValue;

        row.style.display = (matchSearch && matchEstado && matchPlan) ? '' : 'none';
    });
}

/**
 * Seleccionar todos los checkboxes
 */
function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.row-checkbox');

    checkboxes.forEach(cb => {
        cb.checked = selectAll.checked;
    });

    updateBulkActions();
}

/**
 * Actualizar visibilidad de acciones en lote
 */
function updateBulkActions() {
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    const bulkActions = document.getElementById('bulkActions');
    const selectedCount = document.getElementById('selectedCount');

    if (bulkActions) {
        if (checkboxes.length > 0) {
            bulkActions.style.display = 'flex';
            selectedCount.textContent = `${checkboxes.length} seleccionados`;
        } else {
            bulkActions.style.display = 'none';
        }
    }
}

// Escuchar cambios en checkboxes
document.addEventListener('change', (e) => {
    if (e.target.classList.contains('row-checkbox')) {
        updateBulkActions();
    }
});

/**
 * Acciones en lote
 */
async function bulkSuspend() {
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    if (checkboxes.length === 0) return;

    if (!confirm(`¿Suspender ${checkboxes.length} clientes?`)) return;

    for (const cb of checkboxes) {
        await fetch(`/api/cliente/${cb.value}/suspender`, { method: 'POST' });
    }

    showToast(`${checkboxes.length} clientes suspendidos`, 'success');
    setTimeout(() => location.reload(), 500);
}

async function bulkActivate() {
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    if (checkboxes.length === 0) return;

    for (const cb of checkboxes) {
        await fetch(`/api/cliente/${cb.value}/activar`, { method: 'POST' });
    }

    showToast(`${checkboxes.length} clientes activados`, 'success');
    setTimeout(() => location.reload(), 500);
}

async function bulkDelete() {
    const checkboxes = document.querySelectorAll('.row-checkbox:checked');
    if (checkboxes.length === 0) return;

    if (!confirm(`¿Eliminar ${checkboxes.length} clientes? Esta acción no se puede deshacer.`)) return;

    for (const cb of checkboxes) {
        await fetch(`/api/cliente/${cb.value}`, { method: 'DELETE' });
    }

    showToast(`${checkboxes.length} clientes eliminados`, 'success');
    setTimeout(() => location.reload(), 500);
}

/**
 * Exportar clientes
 */
async function exportClientes() {
    try {
        const response = await fetch('/api/clientes');
        const result = await response.json();

        if (result.success) {
            const clientes = result.clientes;

            // Crear CSV
            let csv = 'ID,Nombre,IP,Plan,Download,Upload,Telefono,Direccion,Estado,Fecha Registro\n';

            clientes.forEach(c => {
                csv += `${c.id},"${c.nombre}",${c.ip_address},"${c.plan}",${c.velocidad_download},${c.velocidad_upload},"${c.telefono || ''}","${c.direccion || ''}",${c.estado},"${c.fecha_registro || ''}"\n`;
            });

            // Descargar
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `clientes_${new Date().toISOString().split('T')[0]}.csv`;
            link.click();

            showToast('Archivo exportado', 'success');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error al exportar', 'error');
    }
}

/**
 * Verificar estado de MikroTik
 */
async function checkMikroTikStatus() {
    const statusDiv = document.getElementById('mikrotikStatus');
    if (!statusDiv) return;

    // Mostrar estado de carga
    statusDiv.innerHTML = `
        <div class="status-indicator loading"></div>
        <span>MikroTik: Conectando...</span>
    `;

    try {
        // Usar timeout para evitar espera larga
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 8000);

        const response = await fetch('/api/mikrotik/status', {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const result = await response.json();

        if (result.success && result.connected) {
            statusDiv.innerHTML = `
                <div class="status-indicator online"></div>
                <span>MikroTik: Conectado</span>
            `;

            // Actualizar contador de queues si existe
            const queueCount = document.getElementById('queueCount');
            if (queueCount && result.queue_count !== undefined) {
                queueCount.textContent = result.queue_count;
            }
        } else {
            statusDiv.innerHTML = `
                <div class="status-indicator offline"></div>
                <span>MikroTik: ${result.message || 'Desconectado'}</span>
            `;
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            statusDiv.innerHTML = `
                <div class="status-indicator offline"></div>
                <span>MikroTik: Timeout</span>
            `;
        } else {
            statusDiv.innerHTML = `
                <div class="status-indicator offline"></div>
                <span>MikroTik: Sin configurar</span>
            `;
        }
    }
}

/**
 * Sincronizar e importar queues de MikroTik
 */
async function syncQueues() {
    if (!confirm('¿Importar clientes desde MikroTik?\n\nEsto creará clientes a partir de los queues de tu router. Los clientes con IPs ya registradas serán omitidos.')) {
        return;
    }

    showToast('Sincronizando con MikroTik...', 'warning');

    try {
        const response = await fetch('/api/sync/import-queues', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            showToast(`✅ ${result.importados} clientes importados. ${result.omitidos} omitidos.`, 'success');
            if (result.importados > 0) {
                setTimeout(() => location.reload(), 1500);
            }
        } else {
            showToast(result.error || 'Error al sincronizar', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Error de conexión', 'error');
    }
}

// ============== INICIALIZACIÓN ==============

document.addEventListener('DOMContentLoaded', () => {
    // Verificar estado de MikroTik al cargar
    checkMikroTikStatus();

    // Actualizar cada 60 segundos (el servidor cachea el resultado)
    setInterval(checkMikroTikStatus, 60000);

    // Inicializar velocidades del plan
    updatePlanSpeeds();
});

// Agregar estilos adicionales para detalles de cliente
const detailStyles = document.createElement('style');
detailStyles.textContent = `
    .client-detail-card {
        padding: 10px;
    }
    
    .detail-header {
        display: flex;
        align-items: center;
        gap: 20px;
        margin-bottom: 24px;
        padding-bottom: 20px;
        border-bottom: 1px solid var(--border-color);
    }
    
    .client-avatar.large {
        width: 64px;
        height: 64px;
        font-size: 1.5rem;
    }
    
    .detail-name h3 {
        font-size: 1.25rem;
        margin-bottom: 8px;
    }
    
    .detail-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
    }
    
    .detail-item {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    
    .detail-item.full {
        grid-column: 1 / -1;
    }
    
    .detail-label {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.85rem;
        color: var(--text-muted);
    }
    
    .detail-label i {
        color: var(--primary-light);
    }
`;
document.head.appendChild(detailStyles);
