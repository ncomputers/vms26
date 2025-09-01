// Purpose: handle camera create form and preview

document.addEventListener("DOMContentLoaded", () => {
  const getEl = (id, alt) =>
    document.getElementById(id) || (alt ? document.getElementById(alt) : null);
  const nameEl = getEl("name", "camName");
  const urlEl = getEl("url", "camUrl");
  const typeEl = getEl("type", "camType");
  const profileEl = getEl("profile", "camProfile");
  const orientationEl = getEl("orientation", "camLocation");
  const resolutionEl = getEl("resolution", "camRes");
  const transportEl = getEl("transport", "camStreamType");
  const ppeEl = getEl("ppe", "setPPE");
  const inoutCountEl = getEl("inout_count", "setCount");
  const reverseEl = getEl("reverse");
  const showEl = getEl("show");
  const latEl = getEl("latitude");
  const lngEl = getEl("longitude");

  const testBtn = getEl("testPreview", "testConn");
  const saveBtn = getEl("saveBtn");
  const saveActivateBtn = getEl("saveActivateBtn");
  const toPreviewBtn = getEl("toPreview");
  const confirmCamBtn = getEl("confirmCam");

  const urlHint = getEl("urlHint", "previewError") || getEl("infoMessage");
  const previewImg = getEl("previewImg");
  const previewLog = getEl("previewLog", "previewMetrics");
  const previewModalEl = getEl("previewModal");
  const modal =
    previewModalEl && typeof bootstrap !== "undefined" && bootstrap.Modal
      ? new bootstrap.Modal(previewModalEl)
      : { show() {}, hide() {} };

  toPreviewBtn?.setAttribute("disabled", "disabled");
  confirmCamBtn?.setAttribute("disabled", "disabled");

  let previewUrl = null;

  const allowedSchemes = ["rtsp:", "http:", "https:", "rtmp:", "srt:"];

  function mask(text) {
    return text.replace(/(?<=:\/\/)([^:@\s]+):([^@\/\s]+)@/g, "***:***@");
  }

    function validateUrl() {
      const url = urlEl?.value.trim() || "";
    let msg = "";
    if (!url) {
      msg = "URL required";
    } else {
      try {
        const u = new URL(url);
        if (!allowedSchemes.includes(u.protocol)) {
          msg = "Unsupported scheme";
        }
      } catch {
        msg = "Invalid URL";
      }
    }
      if (urlHint) {
        if (!msg && url.endsWith(".m3u8")) {
          msg = "HLS fallback note: preview may be delayed";
          urlHint.className = "text-warning";
        } else {
          urlHint.className = msg ? "text-danger" : "form-text";
        }
        urlHint.textContent = msg;
      }
      return !msg;
    }

    urlEl?.addEventListener("input", validateUrl);
    if (urlEl) validateUrl();
    [nameEl, urlEl].forEach((el) =>
      el?.addEventListener("input", () => {
        toPreviewBtn?.setAttribute("disabled", "disabled");
        confirmCamBtn?.setAttribute("disabled", "disabled");
      }),
    );

  function clearErrors() {
    document
      .querySelectorAll(".is-invalid")
      .forEach((el) => el.classList.remove("is-invalid"));
    document
      .querySelectorAll(".invalid-feedback")
      .forEach((el) => (el.textContent = ""));
  }

  function applyErrors(errors) {
    errors.forEach((err) => {
      const field = err.loc[err.loc.length - 1];
      const el = document.getElementById(field);
      if (el) {
        el.classList.add("is-invalid");
        const fb = el.parentElement.querySelector(".invalid-feedback");
        if (fb) fb.textContent = err.msg;
      }
    });
  }

  function buildPayload(activate = false) {
      return {
        name: nameEl?.value.trim(),
        url: urlEl?.value.trim(),
        type: typeEl?.value,
        profile: profileEl?.value,
        orientation: orientationEl?.value,
        resolution: resolutionEl?.value,
        transport: transportEl?.value || undefined,
        show: !!showEl?.checked,
        ppe: !!ppeEl?.checked,
        inout_count: !!inoutCountEl?.checked,
        reverse: !!reverseEl?.checked,
        latitude: latEl?.value ? parseFloat(latEl.value) : undefined,
        longitude: lngEl?.value ? parseFloat(lngEl.value) : undefined,
        activate,
      };
    }

  async function startPreview() {
      if (!validateUrl()) return;
      if (testBtn) testBtn.disabled = true;
      if (previewLog) previewLog.textContent = "";
      clearErrors();
    try {
      const body = buildPayload();
      const r = await fetch("/api/cameras/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.status === 422) {
        const data = await r.json();
        applyErrors(data.detail || []);
        return;
      }
      const data = await r.json();
        previewUrl = data.notes;
        if (previewImg) previewImg.src = `${previewUrl}&fps=10`;

        if (data.log && previewLog) {
          const logText = Array.isArray(data.log)
            ? data.log.join("\n")
            : data.log;
          previewLog.textContent = mask(logText);
        }
        modal.show();
        toPreviewBtn?.removeAttribute("disabled");
    } catch (err) {
        if (urlHint) {
          urlHint.textContent = "Preview failed";
          urlHint.className = "text-danger";
        }
    } finally {
        if (testBtn) testBtn.disabled = false;
    }
  }

  function stopPreview() {
      if (!previewUrl) return;
      previewImg?.removeAttribute("src");
      if (previewLog) previewLog.textContent = "";
      previewUrl = null;
  }

    previewModalEl?.addEventListener("hidden.bs.modal", stopPreview);

    testBtn?.addEventListener("click", startPreview);

  async function save(activate = false) {
      if (!validateUrl()) return;
      clearErrors();
      const body = buildPayload();
      const r = await fetch("/api/cameras", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    if (r.status === 422) {
      const data = await r.json();
      applyErrors(data.detail || []);
      return;
    }
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      const msg = err.message || "Save failed";
      if (typeof showToast === "function") showToast(msg, "danger");
      else alert(msg);
      return;
    }
    const data = await r.json();
    if (activate) {
      try {
        const a = await fetch(`/cameras/${data.id}/enabled`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: true }),
        });
        if (!a.ok) {
          const err = await a.json().catch(() => ({}));
          const msg = err.message || "Activation failed";
          if (typeof showToast === "function") showToast(msg, "danger");
          else alert(msg);
        }
      } catch (_) {
        if (typeof showToast === "function")
          showToast("Activation failed", "danger");
      }
    }
      window.location.href = "/cameras";
    }

    saveBtn?.addEventListener("click", () => save(false));
    saveActivateBtn?.addEventListener("click", () => save(true));

    const probeMetrics = async () => {
      const metricsEl = document.getElementById("previewMetrics");
      if (!metricsEl) return;
      metricsEl.textContent = "";
      try {
        const resp = await fetch("/api/cameras/probe");
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          metricsEl.textContent = data.error || "Probe failed";
          return;
        }
        const { metadata = {}, effective_fps, transport, hwaccel } = data;
        metricsEl.textContent = `Codec: ${metadata.codec || ""}, ${metadata.width}x${metadata.height}, FPS: ${effective_fps}, Transport: ${transport}, HWAccel: ${hwaccel}`;
      } catch (err) {
        metricsEl.textContent = "Probe failed";
      }
    };
    // expose for tests when replaced
    window.probeMetrics = probeMetrics;
});
