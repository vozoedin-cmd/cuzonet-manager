(function () {
    "use strict";

    const getCodes = () => {
        const input = document.getElementById("codesInput");
        if (!input) return { total: 0, unique: [] };
        const matches = input.value.match(/\d{6,12}/g) || [];
        return { total: matches.length, unique: [...new Set(matches)] };
    };

    const updateCodesState = () => {
        const { total, unique } = getCodes();
        const count = document.getElementById("codesDetected");
        const detail = document.getElementById("codesDetail");

        if (count) count.textContent = unique.length;
        if (detail) {
            const duplicates = Math.max(0, total - unique.length);
            detail.textContent = duplicates
                ? `${duplicates} duplicado${duplicates === 1 ? "" : "s"} omitido${duplicates === 1 ? "" : "s"}`
                : unique.length
                    ? "Listos para imprimir"
                    : "Esperando códigos";
        }

        document.querySelectorAll("[data-requires-codes]").forEach((button) => {
            button.disabled = unique.length === 0;
        });
    };

    const updateGenerateState = () => {
        const button = document.getElementById("btnAutoGenerate");
        const hint = document.getElementById("genHint");
        if (!button) return;

        const omada = document.getElementById("genOmada")?.value;
        const vendor = document.getElementById("genVendedor")?.value;
        const amount = Number(document.getElementById("genAmount")?.value);
        const time = Number(document.getElementById("genTimeVal")?.value);
        const price = Number(document.getElementById("genPrecio")?.value);

        const faltantes = [];
        if (!omada) faltantes.push("un controlador Omada");
        if (!vendor) faltantes.push("un vendedor");
        if (!(amount > 0)) faltantes.push("una cantidad válida");
        if (!(time > 0)) faltantes.push("una duración válida");
        if (!(price >= 0)) faltantes.push("un precio válido");

        const ready = faltantes.length === 0;
        button.disabled = !ready;
        button.title = ready
            ? "Generar fichas en Omada"
            : `Falta seleccionar/completar: ${faltantes.join(", ")}`;

        if (hint) {
            hint.style.display = ready ? "none" : "block";
            hint.textContent = ready ? "" : `Falta seleccionar/completar: ${faltantes.join(", ")}.`;
        }
    };

    window.pegarCodigosStudio = async function () {
        try {
            const text = await navigator.clipboard.readText();
            const input = document.getElementById("codesInput");
            if (!input) return;
            input.value = text;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            if (typeof window.showToast === "function") {
                window.showToast("Códigos pegados correctamente.", "success");
            }
        } catch (error) {
            document.getElementById("codesInput")?.focus();
            if (typeof window.showToast === "function") {
                window.showToast("Usa Ctrl + V para pegar los códigos.", "info");
            }
        }
    };

    window.limpiarCodigosStudio = function () {
        const input = document.getElementById("codesInput");
        if (!input || !input.value.trim()) return;
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.focus();
    };

    const initialize = () => {
        const codesInput = document.getElementById("codesInput");
        codesInput?.addEventListener("input", updateCodesState);
        codesInput?.setAttribute("aria-describedby", "codesSummary");

        ["genOmada", "genVendedor", "genAmount", "genTimeVal", "genPrecio"].forEach((id) => {
            const field = document.getElementById(id);
            field?.addEventListener("input", updateGenerateState);
            field?.addEventListener("change", updateGenerateState);
        });

        ["businessName", "templateSelector", "colorPicker", "timeInput", "priceInput"].forEach((id) => {
            document.getElementById(id)?.addEventListener("input", () => {
                if (typeof window.renderLivePreview === "function") window.renderLivePreview();
            });
        });

        updateCodesState();
        updateGenerateState();

        window.setTimeout(() => {
            const selected = document.getElementById("genOmada")?.value;
            const status = document.querySelector("#stat_api > div:first-child");
            const ping = document.getElementById("api_ping");
            if (!status || !ping) return;

            status.innerHTML = selected
                ? '<span class="api-dot" aria-hidden="true"></span><span>CONTROLADOR LISTO</span>'
                : '<span class="api-dot api-dot-off" aria-hidden="true"></span><span>SIN CONFIGURAR</span>';
            status.classList.add("api-status-line");
            ping.textContent = selected ? "Conexión disponible" : "Selecciona un controlador";
        }, 1200);
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize);
    } else {
        initialize();
    }
})();
