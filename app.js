document.addEventListener("DOMContentLoaded", () => {
  const search = document.getElementById("commandSearch");
  if (search) {
    const cards = [...document.querySelectorAll(".command-card")];
    search.addEventListener("input", () => {
      const q = search.value.toLowerCase().trim();
      cards.forEach(card => card.style.display = card.dataset.search.toLowerCase().includes(q) ? "" : "none");
    });
  }

  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.tab)?.classList.add("active");
    });
  });

  document.querySelectorAll(".toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      btn.classList.toggle("off");
      btn.textContent = btn.classList.contains("off") ? "OFF" : "ON";
    });
  });

  const save = document.querySelector(".save-settings");
  if (save) {
    save.addEventListener("click", async () => {
      const result = document.getElementById("saveResult");
      result.textContent = "Saving…";
      const payload = {
        prefix: document.getElementById("prefix").value,
        logs_channel: document.getElementById("logs_channel").value
      };
      try {
        const r = await fetch(`/api/dashboard/${window.TESTINY_GUILD_ID}/settings`, {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify(payload)
        });
        const data = await r.json();
        result.textContent = r.ok ? "✓ Saved" : `Error: ${data.error || "Could not save"}`;
      } catch (e) {
        result.textContent = "Could not reach the dashboard API.";
      }
    });
  }

  document.querySelectorAll("[data-action='save-section']").forEach(btn => {
    btn.addEventListener("click", async () => {
      const section = btn.dataset.section;
      const features = [...document.querySelectorAll(`#${section} .feature-row`)].map(row => ({
        name: row.querySelector("span").textContent,
        enabled: !row.querySelector(".toggle").classList.contains("off")
      }));
      btn.textContent = "Saving…";
      try {
        await fetch(`/api/dashboard/${window.TESTINY_GUILD_ID}/settings`, {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({section, features})
        });
        btn.textContent = "✓ Saved";
        setTimeout(() => btn.textContent = `Save ${section[0].toUpperCase()+section.slice(1)} settings`, 1400);
      } catch {
        btn.textContent = "Save failed";
      }
    });
  });
});
