(function () {
    "use strict";

    const notifyCodesChanged = () => {
        document.getElementById("codesInput")?.dispatchEvent(new Event("input", { bubbles: true }));
    };

    const refreshPreview = () => {
        if (typeof window.renderLivePreview === "function") window.renderLivePreview();
    };

    const wrapAsync = (name, after) => {
        const original = window[name];
        if (typeof original !== "function") return;
        window[name] = async function (...args) {
            const result = await original.apply(this, args);
            after();
            return result;
        };
    };

    const wrapSync = (name, after) => {
        const original = window[name];
        if (typeof original !== "function") return;
        window[name] = function (...args) {
            const result = original.apply(this, args);
            after();
            return result;
        };
    };

    wrapAsync("autoGenerateVouchers", notifyCodesChanged);
    wrapAsync("cargarLoteHistorial", () => {
        notifyCodesChanged();
        refreshPreview();
    });
    wrapSync("reimprimirUltimoLote", notifyCodesChanged);
    wrapSync("limpiarFormulario", () => {
        notifyCodesChanged();
        refreshPreview();
    });
    wrapSync("syncPrintFields", refreshPreview);
})();
