import { initPhotoUploader } from "./photo_uploader.js";
import {
  validateEmail,
  showFieldError,
  clearFieldError,
} from "./validation.js";

let gateId = null;

// Initialize gate pass form
export async function initGatepassForm(cfg = {}) {
  // config from data attributes
  const form = document.getElementById("gateForm");
  const printBase =
    cfg.printBase || form.dataset.printBase || "/gatepass/print/";
  const defaultHost = cfg.defaultHost || form.dataset.defaultHost || "";

  // toast helper
  const toastEl = document.getElementById("toast");
  const toastMsg = document.getElementById("toastMsg");
  const showToast = (msg, variant = "primary", allowHtml = false) => {
    if (!toastEl || !toastMsg) {
      console.warn("Toast elements missing");
      return;
    }
    toastEl.className = `toast text-bg-${variant} border-0`;
    if (allowHtml) {
      toastMsg.innerHTML = msg;
    } else {
      toastMsg.textContent = msg;
    }
    bootstrap.Toast.getOrCreateInstance(toastEl).show();
  };

  // state
  const visitorData = {};
  const visitorSuggestions = {};
  const photoData = {};
  const hostData = {};
  const approvalData = {};

  // elements
  const inviteId = document.getElementById("inviteId");
  const vName = document.getElementById("vName");
  const vNameList = document.getElementById("vNameList");
  const vPhone = document.getElementById("vPhone");
  const vEmail = document.getElementById("vEmail");
  const vType = document.getElementById("vType");
  const vPurpose = document.getElementById("vPurpose");
  const vCompany = document.getElementById("vCompany");
  const vValid = document.getElementById("vValid");
  const pad = (n) => String(n).padStart(2, "0");
  const toLocalInputValue = (d) =>
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  let validPicker;
  const refreshValidMin = () => {
    const now = new Date();
    vValid.min = toLocalInputValue(now);
    validPicker?.set("minDate", now);
  };
  refreshValidMin();
  const hName = document.getElementById("hName");
  const hDept = document.getElementById("hDept");
  const needApproval = document.getElementById("needApproval");
  const approverBox = document.getElementById("approverBox");
  const approverEmail = document.getElementById("approverEmail");
  approverBox?.classList.toggle("d-none", !needApproval.checked);
  if (approverEmail) approverEmail.required = needApproval.checked;
  const prevPhoto = document.getElementById("prevPhoto");
  const photoPlaceholder = document.getElementById("photoPlaceholder");
  const pName = document.getElementById("pName");
  const pPhone = document.getElementById("pPhone");
  const pEmail = document.getElementById("pEmail");
  const pType = document.getElementById("pType");
  const pCompany = document.getElementById("pCompany");
  const pHost = document.getElementById("pHost");
  const pDept = document.getElementById("pDept");
  const pPurpose = document.getElementById("pPurpose");
  const pGate = document.getElementById("pGate");
  const pValid = document.getElementById("pValid");
  const pStatus = document.getElementById("pStatus");
  const qrBox = document.getElementById("qrBox");
  const approvalBadge = document.getElementById("approvalBadge");
  const pApproverEmail = document.getElementById("pApproverEmail");
  const printBtn = document.getElementById("printBtn");
  const pdfBtn = document.getElementById("pdfBtn");
  const viewBtn = document.getElementById("viewBtn");
  const shareBtn = document.getElementById("shareBtn");
  const copyPassLinkBtn = document.getElementById("copyPassLinkBtn");
  const copyLinkBtn = document.getElementById("copyLinkBtn");
  const newBtn = document.getElementById("newBtn");
  const confirmBtn = document.getElementById("confirmBtn");
  const saveBtn = document.getElementById("saveBtn");
  const actionButtons = [printBtn, pdfBtn, viewBtn, shareBtn, newBtn];

  const invalidateGate = () => {
    if (gateId === null) return;
    gateId = null;
    if (pGate) pGate.textContent = "Draft";
    actionButtons.forEach((btn) => {
      if (btn) btn.disabled = true;
    });
    copyPassLinkBtn?.classList.add("d-none");
    copyLinkBtn?.classList.add("d-none");
    newBtn?.classList.add("d-none");
  };
  const confirmModalEl = document.getElementById("confirmModal");
  const confirmModal = confirmModalEl
    ? new bootstrap.Modal(confirmModalEl)
    : null;
  if (!confirmModalEl) console.warn("#confirmModal not found");
  const cmPhoto = confirmModalEl?.querySelector("#prevPhoto") || null;
  const cmPhotoPlaceholder =
    confirmModalEl?.querySelector("#photoPlaceholder") || null;
  const cmName = confirmModalEl?.querySelector("#pName") || null;
  const cmPhone = confirmModalEl?.querySelector("#pPhone") || null;
  const cmEmail = confirmModalEl?.querySelector("#pEmail") || null;
  const cmType = confirmModalEl?.querySelector("#pType") || null;
  const cmCompany = confirmModalEl?.querySelector("#pCompany") || null;
  const cmHost = confirmModalEl?.querySelector("#pHost") || null;
  const cmPurpose = confirmModalEl?.querySelector("#pPurpose") || null;
  const cmValid = confirmModalEl?.querySelector("#pValid") || null;

  // enable approval by default
  needApproval.checked = true;
  approverBox.classList.remove("d-none");
  approverEmail.required = true;
  approvalData.needsApproval = true;
  const controls = document.querySelector(".photo-controls");
  const prefix = controls?.dataset.prefix ? `${controls.dataset.prefix}_` : "";
  const getEl = (id) => document.getElementById(`${prefix}${id}`);
  const captureBtn = getEl("capture");
  const uploadBtn = getEl("uploadBtn");
  const videoEl = getEl("preview");
  const photoPreviewEl = getEl("photoPreview");
  const uploadInput = getEl("upload");
  const capturedInput =
    getEl("captured") || document.getElementById("captured");
  const noPhotoChk = getEl("noPhoto") || document.getElementById("noPhoto");
  const toHostBtn = document.getElementById("toHost");
  const retakeBtn = getEl("retake");
  const changePhotoBtn = getEl("changePhoto");
  const brightnessInput = getEl("brightness");

  noPhotoChk?.addEventListener("change", () => {
    invalidateGate();
    if (noPhotoChk.checked) {
      if (capturedInput) capturedInput.value = "";
      photoData.image = null;
      if (prevPhoto) prevPhoto.src = "";
      if (toHostBtn) toHostBtn.disabled = false;
      else console.warn("#toHost not found");
    } else {
      if (toHostBtn) toHostBtn.disabled = !capturedInput?.value;
      else console.warn("#toHost not found");
    }
    updatePreview();
  });

  retakeBtn?.addEventListener("click", () => {
    invalidateGate();
    photoData.image = null;
    if (prevPhoto) prevPhoto.src = "";
    updatePreview();
    if (toHostBtn) toHostBtn.disabled = true;
    else console.warn("#toHost not found");
  });

  // libraries init
  const iti = intlTelInput(vPhone, {
    initialCountry: "in",
    utilsScript:
      "https://cdn.jsdelivr.net/npm/intl-tel-input@19.5.5/build/js/utils.js",
  });
  let typeSelect;
  if (window.TomSelect) {
    try {
      typeSelect = new TomSelect("#vType");
      vType.classList.add("d-none");
    } catch (err) {
      console.error("TomSelect initialization failed", err);
    }
  }
  validPicker = flatpickr("#vValid", {
    enableTime: true,
    dateFormat: "Y-m-d\\TH:i",
    defaultDate: new Date(Date.now() + 3600 * 1000),
    minDate: new Date(),
    onChange: handleValidInput,
  });
  refreshValidMin();

  // live preview updates
  const storeVisitor = () => {
    invalidateGate();
    visitorData.name = vName.value;
    visitorData.phone = iti.getNumber();
    visitorData.email = vEmail.value;
    visitorData.visitor_type = vType.value;
    visitorData.purpose = vPurpose.value;
    visitorData.company = vCompany.value;
    visitorData.valid_to = vValid.value;
  };
  const storeHost = () => {
    invalidateGate();
    hostData.name = hName.value || defaultHost;
    hostData.department = hDept.value;
  };
  const storeApproval = () => {
    invalidateGate();
    approvalData.needsApproval = needApproval.checked;
    approvalData.approverEmail = approverEmail.value.trim();
  };
  const validateApproval = () => {
    if (
      needApproval.checked &&
      !validateEmail(approverEmail.value.trim())
    ) {
      showFieldError(approverEmail, "Valid approver email required");
      return false;
    }
    clearFieldError(approverEmail);
    return true;
  };
  const updatePreview = () => {
    const bindings = [
      [pName, visitorData.name || "", "#pName"],
      [pPhone, visitorData.phone || "", "#pPhone"],
      [pEmail, visitorData.email || "", "#pEmail"],
      [pType, visitorData.visitor_type || "", "#pType"],
      [pCompany, visitorData.company || "", "#pCompany"],
      [pHost, hostData.name || "", "#pHost"],
      [pDept, hostData.department || "", "#pDept"],
      [pPurpose, visitorData.purpose || "", "#pPurpose"],
      [pValid, visitorData.valid_to || "", "#pValid"],
    ];
    bindings.forEach(([el, val, id]) => {
      if (el) {
        el.textContent = val;
        const row = el.closest(".gp-row");
        if (row) row.classList.toggle("d-none", !val);

      } else console.warn(`${id} not found`);
    });

    const imgSrc = photoData.image || prevPhoto?.getAttribute("src") || "";
    const hasImage = !!imgSrc;
    if (hasImage) {
      if (prevPhoto) {
        if (prevPhoto.getAttribute("src") !== imgSrc) {
          prevPhoto.src = imgSrc;
        }
        prevPhoto.classList.remove("d-none");
      } else {
        console.warn("#prevPhoto not found");
      }
      if (photoPlaceholder) {
        photoPlaceholder.classList.add("d-none");
      } else {
        console.warn("#photoPlaceholder not found");
      }
      if (cmPhoto) {
        if (cmPhoto.getAttribute("src") !== imgSrc) {
          cmPhoto.src = imgSrc;
        }
        cmPhoto.classList.remove("d-none");
      } else if (confirmModalEl) {
        console.warn("confirm modal photo not found");
      }
      cmPhotoPlaceholder?.classList.add("d-none");
    } else {
      prevPhoto?.classList.add("d-none");
      if (prevPhoto?.getAttribute("src")) prevPhoto.removeAttribute("src");
      photoPlaceholder?.classList.remove("d-none");
      cmPhoto?.classList.add("d-none");
      cmPhotoPlaceholder?.classList.remove("d-none");
    }

    const cmBindings = [
      [cmName, visitorData.name || "", "#cmName"],
      [cmPhone, visitorData.phone || "", "#cmPhone"],
      [cmEmail, visitorData.email || "", "#cmEmail"],
      [cmType, visitorData.visitor_type || "", "#cmType"],
      [cmCompany, visitorData.company || "", "#cmCompany"],
      [cmHost, hostData.name || "", "#cmHost"],
      [cmPurpose, visitorData.purpose || "", "#cmPurpose"],
      [cmValid, visitorData.valid_to || "", "#cmValid"],
    ];
    cmBindings.forEach(([el, val, id]) => {
      if (el) {
        el.textContent = val;
        const row = el.closest(".gp-row");
        if (row) row.classList.toggle("d-none", !val);

      } else console.warn(`${id} not found`);
    });
    if (pStatus) {
      pStatus.textContent = approvalData.needsApproval
        ? "Pending approval"
        : "Draft";
    }
    if (approvalBadge) {
      const show =
        approvalData.needsApproval &&
        validateEmail(approvalData.approverEmail);
      approvalBadge.classList.toggle("d-none", !show);
      pStatus?.classList.toggle("d-none", show);
      if (show && pApproverEmail)
        pApproverEmail.textContent = approvalData.approverEmail;
      else if (pApproverEmail) pApproverEmail.textContent = "";
    }
  };
  [vName, vPhone, vEmail, vPurpose, vCompany].forEach((el) =>
    el.addEventListener("input", () => {
      clearFieldError(el);
      storeVisitor();
      updatePreview();
    }),
  );
  function handleValidInput() {
    if (vValid.value && new Date(vValid.value) < new Date()) {
      showFieldError(vValid, "Date/time cannot be in the past");
      vValid.value = "";
    } else {
      clearFieldError(vValid);
    }
    storeVisitor();
    updatePreview();
  }
  vValid.addEventListener("input", handleValidInput);
  vType.addEventListener("change", () => {
    clearFieldError(vType);
    storeVisitor();
    updatePreview();
  });
  [hName, hDept].forEach((el) =>
    el.addEventListener("input", () => {
      clearFieldError(el);
      storeHost();
      updatePreview();
    }),
  );
  approverEmail?.addEventListener("input", () => {
    if (needApproval.checked && !validateEmail(approverEmail.value.trim())) {
      showFieldError(approverEmail, "Invalid email");
    } else {
      clearFieldError(approverEmail);
    }
    storeApproval();
    updatePreview();
  });

  storeVisitor();
  storeHost();
  storeApproval();
  updatePreview();

  inviteId.addEventListener("change", async () => {
    const id = inviteId.value.trim();
    if (!id) return;
    try {
      const r = await fetch(`/invite/${encodeURIComponent(id)}`);
      if (r.ok) {
        const d = await r.json();
        if (d.name) vName.value = d.name;
        if (d.phone) {
          iti.setNumber(d.phone);
          vPhone.value = d.phone;
        }
        if (d.email) vEmail.value = d.email;
        if (d.host) hName.value = d.host;
        if (d.purpose) vPurpose.value = d.purpose;
        if (d.expiry) vValid.value = d.expiry;
        if (d.visitor_type) {
          vType.value = d.visitor_type;
          typeSelect?.setValue(d.visitor_type);
        }
        if (d.company) vCompany.value = d.company;
        storeVisitor();
        storeHost();
        updatePreview();
      }
    } catch (err) {
      console.error("invite fetch", err);
    }
  });

  const { uploader: photoHandler, ready: photoReady } = initPhotoUploader({
    videoEl,
    previewEl: photoPreviewEl,
    captureBtn,
    uploadBtn,
    resetBtn: retakeBtn,
    changeBtn: changePhotoBtn,
    uploadInput,
    hiddenInput: capturedInput,
    noPhotoCheckbox: noPhotoChk,
    brightnessInput,
    onCapture: (data) => {
      invalidateGate();
      photoData.image = data;
      if (capturedInput) capturedInput.value = data;
      if (toHostBtn) toHostBtn.disabled = false;
      else console.warn("#toHost not found");
      updatePreview();
    },
  });
  // Wait for cameras to load before enabling controls
  await photoReady;

  function resetGatePass() {
    gateId = null;
    form.reset();
    approverBox?.classList.toggle("d-none", !needApproval.checked);
    if (approverEmail) approverEmail.required = needApproval.checked;
    [
      [pName, "#pName"],
      [pPhone, "#pPhone"],
      [pEmail, "#pEmail"],
      [pType, "#pType"],
      [pCompany, "#pCompany"],
      [pHost, "#pHost"],
      [pDept, "#pDept"],
      [pPurpose, "#pPurpose"],
    ].forEach(([el, id]) => {
      if (el) el.textContent = "";
      else console.warn(`${id} not found`);
    });
    if (pGate) pGate.textContent = "Draft";
    if (pStatus) pStatus.textContent = "Draft";
    if (pValid) pValid.textContent = "";
    if (qrBox) {
      qrBox.innerHTML =
        '<div id="qrPlaceholder" class="qr-placeholder">QR unavailable</div>';
    } else {
      console.warn("#qrBox not found");
    }
    approvalBadge?.classList.add("d-none");
    if (pApproverEmail) pApproverEmail.textContent = "";
    [printBtn, pdfBtn, viewBtn].forEach((btn) => {
      if (btn) btn.disabled = true;
    });
    if (viewBtn) viewBtn.onclick = null;
    copyPassLinkBtn?.classList.add("d-none");
    copyLinkBtn?.classList.add("d-none");
    newBtn?.classList.add("d-none");
    photoHandler.reset();
    if (prevPhoto) {
      prevPhoto.src = "";
      prevPhoto.classList.add("d-none");
    }
    prevPhoto?.classList.remove("skeleton");
    photoPlaceholder?.classList.remove("d-none", "skeleton");
    photoHandler.closeCropper();
    photoHandler.stopStream();
    if (uploadInput) uploadInput.value = "";
    inviteId.value = "";
    if (toHostBtn) toHostBtn.disabled = true;
    else console.warn("#toHost not found");
    if (typeSelect) {
      typeSelect.setValue("");
    }
    iti.setNumber("");
    refreshValidMin();
    validPicker.setDate(new Date(Date.now() + 3600 * 1000));
    clearFieldError(vValid);
    Object.keys(visitorData).forEach((k) => delete visitorData[k]);
    Object.keys(photoData).forEach((k) => delete photoData[k]);
    Object.keys(hostData).forEach((k) => delete hostData[k]);
    hName.value = defaultHost;
    hDept.value = "";
    Object.keys(approvalData).forEach((k) => delete approvalData[k]);
    storeVisitor();
    storeHost();
    storeApproval();
    updatePreview();
    const tabEl = document.querySelector("#visitor-tab");
    if (tabEl) {
      bootstrap.Tab.getOrCreateInstance(tabEl).show();
    }
  }

  // visitor suggestions
  vName.addEventListener("input", async () => {
    const prefix = vName.value.trim();
    if (prefix.length < 2) {
      if (vNameList) vNameList.innerHTML = "";
      else console.warn("#vNameList not found");
      return;
    }
    try {
      const r = await fetch(
        `/api/visitors/suggest?prefix=${encodeURIComponent(prefix)}`,
      );
      if (r.ok && vNameList) {
        const data = await r.json();
        const list = data.suggestions || data;
        vNameList.innerHTML = "";
        (list || []).forEach((item) => {
          const name = item.name || item;
          const opt = document.createElement("option");
          opt.value = name;
          vNameList.appendChild(opt);
          if (typeof item === "object") visitorSuggestions[name] = item;
        });
      } else if (!vNameList) {
        console.warn("#vNameList not found");
      }
    } catch (err) {
      console.error("suggest", err);
    }
  });
  vName.addEventListener("change", () => {
    const info = visitorSuggestions[vName.value];
    if (!info) return;
    if (info.phone) {
      iti.setNumber(info.phone);
      vPhone.value = info.phone;
    }
    if (info.email) vEmail.value = info.email;
    if (info.visitor_type) {
      vType.value = info.visitor_type;
      if (typeSelect) {
        typeSelect.setValue(info.visitor_type);
      }
    }
    if (info.company) vCompany.value = info.company;
    storeVisitor();
    updatePreview();
  });

  // navigation
  document.getElementById("toPhoto")?.addEventListener("click", () => {
    let ok = true;
    if (!vName.value) {
      showFieldError(vName, "Required");
      ok = false;
    }
    if (!iti.isValidNumber()) {
      showFieldError(vPhone, "Invalid phone number");
      ok = false;
    }
    if (!validateEmail(vEmail.value)) {
      showFieldError(vEmail, "Invalid email");
      ok = false;
    }
    if (!vType.value) {
      showFieldError(vType, "Required");
      ok = false;
    }
    if (!vPurpose.value) {
      showFieldError(vPurpose, "Required");
      ok = false;
    }
    if (!vValid.value) {
      showFieldError(vValid, "Required");
      ok = false;
    } else if (new Date(vValid.value) < new Date()) {
      showFieldError(vValid, "Date/time cannot be in the past");
      ok = false;
    }
    if (!ok) {
      showToast("Please fix errors above", "danger");
      return;
    }
    bootstrap.Tab.getOrCreateInstance(
      document.querySelector("#photo-tab"),
    ).show();
  });
  document.getElementById("backVisitor")?.addEventListener("click", () => {
    bootstrap.Tab.getOrCreateInstance(
      document.querySelector("#visitor-tab"),
    ).show();
  });
  toHostBtn?.addEventListener("click", () => {
    if (!capturedInput.value && !(noPhotoChk && noPhotoChk.checked)) {
      showToast("Photo required", "danger");
      return;
    }
    bootstrap.Tab.getOrCreateInstance(
      document.querySelector("#host-tab"),
    ).show();
  });
  document.getElementById("backPhoto")?.addEventListener("click", () => {
    bootstrap.Tab.getOrCreateInstance(
      document.querySelector("#photo-tab"),
    ).show();
  });
  document.getElementById("toReview")?.addEventListener("click", () => {
    let ok = true;
    if (!hName.value && !defaultHost) {
      showFieldError(hName, "Required");
      ok = false;
    }
    if (!validateApproval()) ok = false;
    if (!ok) {
      showToast("Please fix errors above", "danger");
      return;
    }

    bootstrap.Tab.getOrCreateInstance(
      document.querySelector("#review-tab"),
    ).show();
    updatePreview();
  });
  document.getElementById("backHost")?.addEventListener("click", () => {
    bootstrap.Tab.getOrCreateInstance(
      document.querySelector("#host-tab"),
    ).show();
  });

  // approval toggle
  needApproval.addEventListener("change", () => {
    approverBox.classList.toggle("d-none", !needApproval.checked);
    approverEmail.required = needApproval.checked;
    if (!needApproval.checked) {
      approverEmail.value = "";
      clearFieldError(approverEmail);
    }
    storeApproval();
    updatePreview();
  });

  // confirm save
  confirmBtn?.addEventListener("click", () => {
    let ok = true;
    if (!vName.value) {
      showFieldError(vName, "Required");
      ok = false;
    }
    if (!iti.isValidNumber()) {
      showFieldError(vPhone, "Invalid phone number");
      ok = false;
    }
    if (!validateEmail(vEmail.value)) {
      showFieldError(vEmail, "Invalid email");
      ok = false;
    }
    if (!vType.value) {
      showFieldError(vType, "Required");
      ok = false;
    }
    if (!vPurpose.value) {
      showFieldError(vPurpose, "Required");
      ok = false;
    }
    if (!vValid.value) {
      showFieldError(vValid, "Required");
      ok = false;
    }
    if (!capturedInput.value && !(noPhotoChk && noPhotoChk.checked)) {
      showToast("Photo required", "danger");
      ok = false;
    }
    if (!hName.value && !defaultHost) {
      showFieldError(hName, "Required");
      ok = false;
    }
    if (!validateApproval()) ok = false;
    if (!ok) {
      showToast("Please fix errors above", "danger");
      return;
    }

    updatePreview();
    confirmModal.show();
  });

  // save
  async function handleSave() {
    try {
      saveBtn.disabled = true;
      actionButtons.forEach((btn) => {
        if (btn) btn.disabled = true;
      });
      copyPassLinkBtn?.classList.add("d-none");
      copyLinkBtn?.classList.add("d-none");
      newBtn?.classList.add("d-none");
      confirmModal?.hide();
      storeVisitor();
      storeHost();
      storeApproval();
      if (!validateApproval()) {
        showToast("Valid approver email required", "danger");
        return;
      }
      if (qrBox) {
        qrBox.innerHTML = "";
        const loader = document.createElement("div");
        loader.className = "qr-placeholder skeleton";
        qrBox.appendChild(loader);
      }
      if (prevPhoto && !prevPhoto.classList.contains("d-none")) {
        prevPhoto.classList.add("skeleton");
      } else if (photoPlaceholder) {
        photoPlaceholder.classList.add("skeleton");
      }
      const fd = new FormData();
      fd.append("name", visitorData.name);
      fd.append("phone", visitorData.phone);
      fd.append("email", visitorData.email);
      fd.append("visitor_type", visitorData.visitor_type);
      fd.append("purpose", visitorData.purpose);
      fd.append("company_name", visitorData.company);
      fd.append("valid_to", visitorData.valid_to);
      fd.append("host", hostData.name);
      fd.append("host_department", hostData.department);
      fd.append("needs_approval", approvalData.needsApproval ? "on" : "");
      fd.append("approver_email", approvalData.approverEmail);
      fd.append("captured", capturedInput.value);
      fd.append("invite_id", inviteId.value);
      if (noPhotoChk?.checked) {
        fd.append("no_photo", "on");
      }
      const r = await fetch("/gatepass/create", { method: "POST", body: fd });
      if (!r.ok) {
        const err = await r.text();
        showToast(`Save failed — ${err}`, "danger");
        return;
      }
      const d = await r.json();
      if (pGate) pGate.textContent = d.gate_id;
      else console.warn("#pGate not found");
      if (pStatus) pStatus.textContent = d.status || "Created";
      if (approvalBadge) {
        const show = d.status === "pending" && approvalData.approverEmail;
        approvalBadge.classList.toggle("d-none", !show);
        if (show && pApproverEmail) {
          pApproverEmail.textContent = approvalData.approverEmail;
        } else if (pApproverEmail) pApproverEmail.textContent = "";
      }
      if (qrBox) {
        qrBox.querySelector(".skeleton")?.remove();
        qrBox.querySelector("#qrPlaceholder")?.remove();
        let qrImg = qrBox.querySelector("img");
        if (!qrImg) {
          qrImg = document.createElement("img");
          qrImg.alt = "QR";
          qrBox.appendChild(qrImg);
        }
        qrImg.src = d.qr_img;
        qrImg.style.cursor = "pointer";
        qrImg.onclick = () =>
          window.open(d.digital_pass_url || `/gatepass/view/${d.gate_id}`, "_blank");
      } else {
        console.warn("#qrBox not found");
      }
      prevPhoto?.classList.remove("skeleton");
      photoPlaceholder?.classList.remove("skeleton");

      const printHandler = () => window.open(printBase + d.gate_id, "_blank");
      const pdfHandler = () => {
        const preview = document.getElementById("previewCard");
        const hidden = [];
        preview.querySelectorAll(".no-print").forEach((el) => {
          hidden.push([el, el.style.display]);
          el.style.display = "none";
        });
        html2pdf()
          .from(preview)
          .save(`gatepass_${d.gate_id}.pdf`)
          .then(() => hidden.forEach(([el, ds]) => (el.style.display = ds)));
      };
      const viewHandler = () =>
        window.open(`/gatepass/view/${d.gate_id}`, "_blank");
      const copyPassLinkHandler = () => {
        navigator.clipboard.writeText(
          `${location.origin}/gatepass/view/${d.gate_id}`,
        );

        showToast("Pass link copied", "success");
      };
      const shareHandler = async () => {
        const url = `${location.origin}/gatepass/view/${d.gate_id}`;
        try {
          await navigator.clipboard.writeText(url);
        } catch {}
        if (navigator.share) {
          try {
            await navigator.share({ title: "Gate Pass", url });
          } catch {}
        } else {
          window.open(
            `mailto:?subject=Gate%20Pass&body=${encodeURIComponent(url)}`,
            "_blank",
          );
          window.open(
            `https://wa.me/?text=${encodeURIComponent(url)}`,
            "_blank",
          );
          showToast("Link copied", "success");
        }
      };

      [printBtn, pdfBtn, viewBtn, shareBtn].forEach((btn) => {
        if (btn) btn.disabled = false;
      });

      if (printBtn) printBtn.onclick = printHandler;
      if (pdfBtn) pdfBtn.onclick = pdfHandler;
      if (viewBtn) viewBtn.onclick = viewHandler;
      if (shareBtn) shareBtn.onclick = shareHandler;

      if (copyPassLinkBtn) {
        copyPassLinkBtn.classList.remove("d-none");
        copyPassLinkBtn.onclick = copyPassLinkHandler;
      }
      if (d.approval_url && copyLinkBtn) {
        copyLinkBtn.classList.remove("d-none");
        copyLinkBtn.onclick = () => {
          navigator.clipboard.writeText(d.approval_url);
          showToast("Approval link copied", "success");
        };
      }
      if (d.approval_url) {
        showToast(`Approval email sent to ${approvalData.approverEmail}`, "success");
        console.log(
          `Approval email sent to ${approvalData.approverEmail} at ${new Date().toISOString()}`,
        );
      }
      const toastActions = `Gate Pass #${d.gate_id} created – What do you want to do next?<div class="mt-2 pt-2 border-top d-flex flex-wrap gap-2"><button class="btn btn-sm btn-light" id="toastPrint">Print</button><button class="btn btn-sm btn-light" id="toastView">View</button><button class="btn btn-sm btn-light" id="toastPdf">Download PDF</button><button class="btn btn-sm btn-light" id="toastShare">Share</button><button class="btn btn-sm btn-light" id="toastCopy">Copy Link</button></div>`;
      showToast(toastActions, "success", true);
      document
        .getElementById("toastPrint")
        ?.addEventListener("click", printHandler);
      document
        .getElementById("toastView")
        ?.addEventListener("click", viewHandler);
      document
        .getElementById("toastPdf")
        ?.addEventListener("click", pdfHandler);
      document
        .getElementById("toastShare")
        ?.addEventListener("click", shareHandler);
      document
        .getElementById("toastCopy")
        ?.addEventListener("click", copyPassLinkHandler);


      if (newBtn) {
        newBtn.classList.remove("d-none");
        newBtn.disabled = false;
        newBtn.onclick = resetGatePass;
      }
    } catch (err) {
      showToast(`Save failed — ${err}`, "danger");
    } finally {
      saveBtn.disabled = false;
    }
  }

  const bindSaveOnce = () => {
    saveBtn.removeEventListener("click", handleSave);
    saveBtn.addEventListener("click", handleSave, { once: true });
  };

  if (confirmModalEl) {
    confirmModalEl.addEventListener("show.bs.modal", bindSaveOnce);
    confirmModalEl.addEventListener("hide.bs.modal", () =>
      saveBtn.removeEventListener("click", handleSave),
    );
  }
}
