// Load and manage identity profile data without face operations

document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("identityProfile");
    if (!root) {
        return;
    }
    const id = root.dataset.id;
    const nameInput = document.getElementById("identityName");
    const companyInput = document.getElementById("identityCompany");
    const tagsInput = document.getElementById("identityTags");
    const visitTimeline = document.getElementById("visitTimeline");
    const cameraList = document.getElementById("cameraList");

    function loadProfile() {
        fetch(`/api/identities/${id}`)
            .then((r) => r.json())
            .then((data) => {
                nameInput.value = data.name || "";
                companyInput.value = data.company || "";
                tagsInput.value = (data.tags || []).join(", ");

                visitTimeline.innerHTML = "";
                (data.visits || []).forEach((v) => {
                    const li = document.createElement("li");
                    li.className = "list-group-item";
                    li.textContent = v;
                    visitTimeline.appendChild(li);
                });

                cameraList.innerHTML = "";
                (data.cameras || []).forEach((c) => {
                    const li = document.createElement("li");
                    li.className = "list-group-item";
                    li.textContent = c;
                    cameraList.appendChild(li);
                });
            });
    }

    document.getElementById("saveIdentity").addEventListener("click", () => {
        const payload = {
            name: nameInput.value,
            company: companyInput.value,
            tags: tagsInput.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
        };
        fetch(`/api/identities/${id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        }).then(loadProfile);
    });

    loadProfile();
});
