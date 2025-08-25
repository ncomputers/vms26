// Purpose: client-side webcam face detection using server InstaFace model
let stream = null;
let timer = null;

const video = document.getElementById("video");
const canvas = document.getElementById("overlay");
const addBtn = document.getElementById("addFaceBtn");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");
const captureBtn = document.getElementById("captureBtn");
const controls = document.getElementById("controls");
const statusEl = document.getElementById("status");
const knownFacesEl = document.getElementById("knownFaces");
const searchFile = document.getElementById("searchFile");
const searchThreshold = document.getElementById("searchThreshold");
const searchBtn = document.getElementById("searchBtn");
const searchResults = document.getElementById("searchResults");
const searchPreview = document.getElementById("searchPreview");
const configEl = document.getElementById("face-db-config");
window.enableFaceMatching = configEl?.dataset.enableFaceMatching === "true";

let faceMap = {};

const capture = document.createElement("canvas");
const ctx = canvas.getContext("2d");
const cctx = capture.getContext("2d");

async function start() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
  } catch (err) {
    statusEl.textContent = "Camera access denied or unavailable.";
    return;
  }
  statusEl.textContent = "";
  video.srcObject = stream;
  await video.play();
  const { videoWidth, videoHeight } = video;
  canvas.width = videoWidth;
  canvas.height = videoHeight;
  capture.width = videoWidth;
  capture.height = videoHeight;
  video.classList.remove("d-none");
  canvas.classList.remove("d-none");
  startBtn.disabled = true;
  captureBtn.disabled = false;
  stopBtn.disabled = false;
  tick();
}

async function tick() {
  if (!stream) return;
  cctx.drawImage(video, 0, 0, capture.width, capture.height);
  const b64 = capture.toDataURL("image/jpeg", 0.7).split(",")[1];
  try {
    const resp = await fetch("/process_frame", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: b64 }),
    });
    const data = await resp.json();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (Array.isArray(data.faces)) {
      data.faces.forEach((f) => {
        const [x, y, w, h] = f.box;
        ctx.strokeStyle = "red";
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        if (typeof f.confidence === "number") {
          const confText = Number(f.confidence).toFixed(2);
          ctx.fillStyle = "red";
          ctx.font = "16px sans-serif";
          ctx.fillText(confText, x, y > 10 ? y - 5 : 10);
        }
      });
    }
  } catch (err) {
    console.error("process_frame failed", err);
  }
  timer = setTimeout(tick, 200);
}

function stop() {
  if (timer) clearTimeout(timer);
  timer = null;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  startBtn.disabled = false;
  captureBtn.disabled = true;
  stopBtn.disabled = true;
}

addBtn.addEventListener("click", () => {
  addBtn.classList.add("d-none");
  controls.classList.remove("d-none");
  start();
});

startBtn.addEventListener("click", start);
stopBtn.addEventListener("click", stop);

captureBtn?.addEventListener("click", () => {
  cctx.drawImage(video, 0, 0, capture.width, capture.height);
  capture.toBlob(async (blob) => {
    if (!blob) return;
    const name = prompt("Enter name for this face:");
    if (!name) return;
    const fd = new FormData();
    fd.append("visitor_id", name);
    fd.append("image", blob, "capture.jpg");
    try {
      const resp = await fetch("/api/faces/add", { method: "POST", body: fd });
      const data = await resp.json();
      if (resp.ok && data.added) {
        loadFaces();
      } else {
        statusEl.textContent = "Failed to add face";
      }
    } catch (err) {
      console.error("add face failed", err);
    }
  }, "image/jpeg");
});

async function loadFaces() {
  if (!knownFacesEl) return;
  try {
    const resp = await fetch("/api/faces?status=known&limit=100");
    const data = await resp.json();
    knownFacesEl.innerHTML = "";
    faceMap = {};
    if (Array.isArray(data.items)) {
      data.items.forEach((f) => {
        faceMap[f.id] = f;
        const imgSrc = f.thumbnail_url || "/static/img/visitor_placeholder.svg";
        const img = `<img src="${imgSrc}" class="img-thumbnail mb-2" width="120" alt="face">`;
        knownFacesEl.insertAdjacentHTML(
          "beforeend",
          `
          <div class="col-md-3 text-center mb-3">
            ${img}
            <div>${f.name || f.id}</div>
          </div>`,
        );
      });
    }
  } catch (err) {
    console.error("load faces failed", err);
  }
}

searchBtn?.addEventListener("click", async () => {
  const file = searchFile?.files?.[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("image", file);
  fd.append("threshold", searchThreshold.value || "0");
  if (searchPreview) {
    if (searchPreview.src) URL.revokeObjectURL(searchPreview.src);
    searchPreview.src = "";
    searchPreview.classList.add("d-none");
  }
  searchFile.value = "";
  try {
    const resp = await fetch("/api/faces/search", { method: "POST", body: fd });
    const data = await resp.json();
    searchResults.innerHTML = "";
    if (Array.isArray(data.matches)) {
      data.matches.forEach((m) => {
        const info = faceMap[m.id] || {};
        const imgSrc = m.thumbnail_url || "/static/img/visitor_placeholder.svg";
        const name = info.name || m.id;
        const img = `<img src="${imgSrc}" class="img-thumbnail mb-2" width="120" alt="face">`;
        searchResults.insertAdjacentHTML(
          "beforeend",
          `
          <div class="col-md-3 text-center mb-3">
            ${img}
            <div>${name}</div>
            <div class="text-muted">${m.score.toFixed(2)}</div>
          </div>`,
        );
      });
    }
  } catch (err) {
    console.error("search failed", err);
  }
});

searchFile?.addEventListener("change", () => {
  if (!searchPreview) return;
  const file = searchFile.files?.[0];
  if (file) {
    const url = URL.createObjectURL(file);
    searchPreview.src = url;
    searchPreview.classList.remove("d-none");
  } else {
    if (searchPreview.src) URL.revokeObjectURL(searchPreview.src);
    searchPreview.src = "";
    searchPreview.classList.add("d-none");
  }
});

document.addEventListener("DOMContentLoaded", loadFaces);
