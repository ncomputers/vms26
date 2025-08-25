export function initSuggestions() {
  const nameField = document.querySelector('input[name="name"]');
  const phoneField = document.getElementById("phone");
  const emailField = document.querySelector('input[name="email"]');

  async function fetchSuggestions(prefix) {
    if (prefix.length < 2) return [];
    const resp = await fetch(
      "/api/visitors/suggest?name_prefix=" + encodeURIComponent(prefix),
    );
    return resp.ok ? resp.json() : [];
  }

  function updateLists(items) {
    const nlist = document.getElementById("nameSuggestions");
    const plist = document.getElementById("phoneSuggestions");
    if (!nlist || !plist) return;
    nlist.innerHTML = "";
    plist.innerHTML = "";
    items.forEach((it) => {
      const no = document.createElement("option");
      no.value = it.name;
      nlist.appendChild(no);
      const po = document.createElement("option");
      po.value = it.phone;
      plist.appendChild(po);
    });
  }

  function debounce(fn, delay) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), delay);
    };
  }

  const debouncedSuggest = debounce(async (field, val) => {
    const start = field.selectionStart;
    const end = field.selectionEnd;
    const items = await fetchSuggestions(val);
    updateLists(items);
    field.setSelectionRange(start, end);
    field.focus();
  }, 300);

  nameField.addEventListener("input", (e) => {
    debouncedSuggest(e.target, e.target.value);
  });

  phoneField.addEventListener("input", (e) => {
    const val = e.target.value.replace(/\D/g, "");
    debouncedSuggest(e.target, val);
  });

  phoneField.addEventListener("change", async (e) => {
    const ph = e.target.value.replace(/\D/g, "");
    if (ph.length < 3) return;
    const r = await fetch("/invite/lookup?phone=" + ph);
    if (r.ok) {
      const d = await r.json();
      if (d.name && !nameField.value) {
        nameField.value = d.name;
      }
      if (d.email && !emailField.value) {
        emailField.value = d.email;
      }
      document.getElementById("lookupInfo").textContent = d.last_id
        ? `ID: ${d.last_id} Visits: ${d.visits}`
        : "";
    }
  });
}
