const urlsEl = document.getElementById("urls");
const defaultQualityEl = document.getElementById("defaultQuality");
const analyzeBtn = document.getElementById("analyzeBtn");
const globalError = document.getElementById("globalError");
const resultsSection = document.getElementById("resultsSection");
const resultsTitle = document.getElementById("resultsTitle");
const resultsList = document.getElementById("resultsList");
const downloadAllBtn = document.getElementById("downloadAllBtn");

let currentItems = [];

function setLoading(isLoading) {
  analyzeBtn.disabled = isLoading;
  analyzeBtn.querySelector(".btn-label").textContent = isLoading ? "Analyzing..." : "Analyze";
  analyzeBtn.querySelector(".spinner").classList.toggle("hidden", !isLoading);
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "";
  seconds = Math.round(seconds);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

function qualityOptions(item) {
  const qualities = item.qualities && item.qualities.length ? item.qualities : ["best"];
  const preferred = defaultQualityEl.value;
  return qualities
    .map((q) => `<option value="${q}" ${q === preferred ? "selected" : ""}>${q}</option>`)
    .join("");
}

function renderItem(item, index) {
  if (item.error) {
    return `
      <div class="video-card errored" data-index="${index}">
        <div class="video-info">
          <p class="video-title">${escapeHtml(item.url)}</p>
          <p class="card-error">${escapeHtml(item.error)}</p>
        </div>
      </div>`;
  }

  const meta = [];
  if (item.uploader) meta.push(escapeHtml(item.uploader));
  if (item.duration) meta.push(formatDuration(item.duration));

  return `
    <div class="video-card" data-index="${index}">
      <img class="video-thumb" src="${item.thumbnail || ""}" alt="" loading="lazy" onerror="this.style.visibility='hidden'" />
      <div class="video-info">
        <p class="video-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</p>
        <div class="video-meta">
          ${item.source_playlist ? `<span class="playlist-tag">${escapeHtml(item.source_playlist)}</span>` : ""}
          ${meta.map((m) => `<span>${m}</span>`).join("")}
        </div>
      </div>
      <div class="video-actions">
        <select class="quality-select">${qualityOptions(item)}</select>
        <button class="dl-btn" data-action="download">Download</button>
      </div>
    </div>`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function render() {
  resultsList.innerHTML = currentItems.map(renderItem).join("");
  const downloadable = currentItems.filter((i) => !i.error).length;
  resultsTitle.textContent = `Results (${currentItems.length})`;
  downloadAllBtn.classList.toggle("hidden", downloadable < 2);
}

function triggerDownload(url, quality) {
  const params = new URLSearchParams({ url, quality: quality || "best" });
  const link = document.createElement("a");
  link.href = `/api/download?${params.toString()}`;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

resultsList.addEventListener("click", (e) => {
  const btn = e.target.closest('[data-action="download"]');
  if (!btn) return;
  const card = btn.closest(".video-card");
  const index = Number(card.dataset.index);
  const item = currentItems[index];
  const quality = card.querySelector(".quality-select")?.value;
  triggerDownload(item.url, quality);
  btn.textContent = "Started ✓";
  btn.classList.add("done");
});

downloadAllBtn.addEventListener("click", async () => {
  const cards = [...resultsList.querySelectorAll(".video-card:not(.errored)")];
  for (const card of cards) {
    const index = Number(card.dataset.index);
    const item = currentItems[index];
    const quality = card.querySelector(".quality-select")?.value;
    triggerDownload(item.url, quality);
    const btn = card.querySelector(".dl-btn");
    if (btn) {
      btn.textContent = "Started ✓";
      btn.classList.add("done");
    }
    // Stagger requests so the browser doesn't block "multiple downloads at once".
    await new Promise((r) => setTimeout(r, 900));
  }
});

analyzeBtn.addEventListener("click", async () => {
  globalError.classList.add("hidden");
  const urls = urlsEl.value
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);

  if (!urls.length) {
    globalError.textContent = "Paste at least one YouTube link.";
    globalError.classList.remove("hidden");
    return;
  }

  setLoading(true);
  resultsSection.classList.add("hidden");

  try {
    const res = await fetch("/api/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Unknown error.");
    }
    currentItems = data.items || [];
    render();
    resultsSection.classList.remove("hidden");
  } catch (err) {
    globalError.textContent = err.message || "Something went wrong.";
    globalError.classList.remove("hidden");
  } finally {
    setLoading(false);
  }
});

urlsEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    analyzeBtn.click();
  }
});
