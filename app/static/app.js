const urlsEl = document.getElementById("urls");
const clearBtn = document.getElementById("clearBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const globalError = document.getElementById("globalError");
const validationHint = document.getElementById("validationHint");
const skeletonSection = document.getElementById("skeletonSection");
const resultsSection = document.getElementById("resultsSection");
const resultsTitle = document.getElementById("resultsTitle");
const resultsList = document.getElementById("resultsList");
const downloadAllBtn = document.getElementById("downloadAllBtn");
const rateLimitHint = document.getElementById("rateLimitHint");
const selectAllCheckbox = document.getElementById("selectAllCheckbox");
const selectAllLabel = document.getElementById("selectAllLabel");
const bulkQualityLabel = document.getElementById("bulkQualityLabel");
const bulkQualitySelect = document.getElementById("bulkQualitySelect");
const searchView = document.getElementById("searchView");
const downloadsView = document.getElementById("downloadsView");
const downloadsList = document.getElementById("downloadsList");
const backBtn = document.getElementById("backBtn");
const langButton = document.getElementById("langButton");
const langButtonLabel = document.getElementById("langButtonLabel");
const langMenu = document.getElementById("langMenu");

let currentItems = [];
let downloadIdCounter = 0;
const downloads = new Map(); // id -> entry

// ---------- i18n wiring ----------

function applyStaticTranslations() {
  document.documentElement.lang = getLang();
  document.title = t("pageTitle");
  document.querySelector('meta[name="description"]')?.setAttribute("content", t("metaDescription"));

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
}

function populateLangMenu() {
  langButtonLabel.textContent = TRANSLATIONS[getLang()].langName;
  langMenu.innerHTML = SUPPORTED_LANGS.map(
    (code) =>
      `<li role="option" data-lang="${code}" aria-selected="${code === getLang()}">${TRANSLATIONS[code].langName}</li>`
  ).join("");
}

function closeLangMenu() {
  langMenu.classList.add("hidden");
  langButton.setAttribute("aria-expanded", "false");
}

function openLangMenu() {
  langMenu.classList.remove("hidden");
  langButton.setAttribute("aria-expanded", "true");
}

langButton.addEventListener("click", (e) => {
  e.stopPropagation();
  if (langMenu.classList.contains("hidden")) openLangMenu();
  else closeLangMenu();
});

langMenu.addEventListener("click", (e) => {
  const li = e.target.closest("[data-lang]");
  if (!li) return;
  setLang(li.dataset.lang);
  populateLangMenu();
  closeLangMenu();
  applyStaticTranslations();
  render();
  renderDownloadsList();
});

document.addEventListener("click", (e) => {
  if (!langMenu.classList.contains("hidden") && !e.target.closest(".lang-switcher")) {
    closeLangMenu();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !langMenu.classList.contains("hidden")) {
    closeLangMenu();
    langButton.focus();
  }
});

populateLangMenu();
applyStaticTranslations();

// ---------- Helpers ----------

function setLoading(isLoading) {
  analyzeBtn.disabled = isLoading;
  analyzeBtn.querySelector(".btn-label").textContent = isLoading ? t("analyzing") : t("analyze");
  analyzeBtn.querySelector(".spinner").classList.toggle("hidden", !isLoading);
  skeletonSection.classList.toggle("hidden", !isLoading);
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

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatEta(seconds) {
  if (!isFinite(seconds) || seconds < 0) return null;
  if (seconds < 1) return t("almostDone");
  if (seconds < 60) return t("secLeft", Math.round(seconds));
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return t("minSecLeft", m, s);
}

const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "music.youtube.com",
  "youtu.be",
  "www.youtu.be",
]);

function isLikelyYoutubeUrl(str) {
  try {
    return YOUTUBE_HOSTS.has(new URL(str).hostname.toLowerCase());
  } catch {
    return false;
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------- View navigation (search <-> downloads) ----------

function renderView(view) {
  const showDownloads = view === "downloads";
  downloadsView.classList.toggle("hidden", !showDownloads);
  searchView.classList.toggle("hidden", showDownloads);
}

function goToDownloads() {
  renderView("downloads");
  if (location.hash !== "#downloads") {
    history.pushState({ view: "downloads" }, "", "#downloads");
  }
}

function goToSearch() {
  renderView("search");
  if (location.hash === "#downloads") {
    history.pushState({ view: "search" }, "", location.pathname + location.search);
  }
}

backBtn.addEventListener("click", goToSearch);

window.addEventListener("popstate", (e) => {
  const view = e.state?.view || (location.hash === "#downloads" ? "downloads" : "search");
  renderView(view);
});

// ---------- Search / results ----------

function qualityOptions(item) {
  const qualities = item.qualities && item.qualities.length ? item.qualities : ["best"];
  const preferred = qualities.includes("1080p") ? "1080p" : qualities[0];
  return qualities
    .map((q) => `<option value="${q}" ${q === preferred ? "selected" : ""}>${q === "best" ? t("bestAvailable") : q}</option>`)
    .join("");
}

function renderItem(item, index, showCheckbox) {
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
      <div class="video-card-row">
        ${showCheckbox ? `<input type="checkbox" class="video-checkbox" ${item.selected ? "checked" : ""} aria-label="${t("selectThisVideo")}" />` : ""}
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
          <button class="dl-btn" data-action="download">${t("download")}</button>
        </div>
      </div>
    </div>`;
}

function selectableItems() {
  return currentItems.filter((i) => !i.error);
}

function syncSelectAllCheckbox() {
  const items = selectableItems();
  const selectedCount = items.filter((i) => i.selected).length;
  selectAllCheckbox.checked = items.length > 0 && selectedCount === items.length;
  selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < items.length;
}

function syncDownloadAllLabel() {
  const selectedCount = selectableItems().filter((i) => i.selected).length;
  downloadAllBtn.textContent = t("downloadSelected", selectedCount);
  downloadAllBtn.disabled = selectedCount === 0;

  if (selectedCount > DOWNLOAD_RATE_LIMIT) {
    rateLimitHint.textContent = t("rateLimitWarning", selectedCount, DOWNLOAD_RATE_LIMIT);
    rateLimitHint.classList.remove("hidden");
  } else {
    rateLimitHint.classList.add("hidden");
  }
}

function render() {
  const downloadable = selectableItems().length;
  const showCheckbox = downloadable >= 2;
  resultsList.innerHTML = currentItems.map((item, index) => renderItem(item, index, showCheckbox)).join("");
  resultsTitle.textContent = t("results", currentItems.length);
  downloadAllBtn.classList.toggle("hidden", downloadable < 2);
  selectAllLabel.classList.toggle("hidden", downloadable < 2);
  bulkQualityLabel.classList.toggle("hidden", downloadable < 2);
  bulkQualitySelect.value = "";
  syncSelectAllCheckbox();
  syncDownloadAllLabel();
}

bulkQualitySelect.addEventListener("change", () => {
  const quality = bulkQualitySelect.value;
  if (!quality) return;
  resultsList.querySelectorAll(".video-card:not(.errored) .quality-select").forEach((select) => {
    if ([...select.options].some((o) => o.value === quality)) {
      select.value = quality;
    }
  });
});

resultsList.addEventListener("click", (e) => {
  const btn = e.target.closest('[data-action="download"]');
  if (!btn) return;
  const card = btn.closest(".video-card");
  const index = Number(card.dataset.index);
  const item = currentItems[index];
  const quality = card.querySelector(".quality-select")?.value;
  const entry = createDownloadEntry(item, quality);
  goToDownloads();
  runDownload(entry);
});

resultsList.addEventListener("change", (e) => {
  if (!e.target.classList.contains("video-checkbox")) return;
  const card = e.target.closest(".video-card");
  const index = Number(card.dataset.index);
  currentItems[index].selected = e.target.checked;
  syncSelectAllCheckbox();
  syncDownloadAllLabel();
});

selectAllCheckbox.addEventListener("change", () => {
  const checked = selectAllCheckbox.checked;
  selectableItems().forEach((i) => (i.selected = checked));
  render();
});

// ---------- Downloads view ----------

function extractFilename(contentDisposition) {
  if (!contentDisposition) return null;
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) return decodeURIComponent(utf8Match[1]);
  const asciiMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return asciiMatch ? asciiMatch[1] : null;
}

function createDownloadEntry(item, quality) {
  const entry = {
    id: ++downloadIdCounter,
    item,
    quality,
    status: "starting", // starting | waiting | downloading | done | error | cancelled
    received: 0,
    total: 0,
    statusText: t("waitingForServer"),
    controller: null,
  };
  downloads.set(entry.id, entry);
  renderDownloadsList();
  return entry;
}

function renderDownloadRow(entry) {
  const pct = entry.total ? Math.round((entry.received / entry.total) * 100) : 0;
  let actionHtml;
  if (entry.status === "starting" || entry.status === "downloading" || entry.status === "waiting") {
    actionHtml = `<button class="dl-btn" data-action="cancel-dl" data-id="${entry.id}">${t("cancel")}</button>`;
  } else if (entry.status === "error" || entry.status === "cancelled") {
    actionHtml = `<button class="dl-btn" data-action="retry-dl" data-id="${entry.id}">${t("retry")}</button>`;
  } else {
    actionHtml = `<button class="dl-btn done" disabled>${t("done")}</button>`;
  }

  return `
    <div class="video-card" data-id="${entry.id}">
      <div class="video-card-row">
        <img class="video-thumb" src="${entry.item.thumbnail || ""}" alt="" onerror="this.style.visibility='hidden'" />
        <div class="video-info">
          <p class="video-title" title="${escapeHtml(entry.item.title)}">${escapeHtml(entry.item.title)}</p>
        </div>
        <div class="video-actions">${actionHtml}</div>
      </div>
      <div class="progress-track ${entry.status === "error" ? "error" : ""} ${isIndeterminate(entry) ? "indeterminate" : ""}">
        <div class="progress-fill" style="width:${pct}%"></div>
      </div>
      <p class="progress-label">${escapeHtml(entry.statusText)}</p>
    </div>`;
}

function isIndeterminate(entry) {
  return entry.status === "starting" || entry.status === "waiting";
}

function renderDownloadsList() {
  const entries = [...downloads.values()].reverse();
  downloadsList.innerHTML =
    entries.map(renderDownloadRow).join("") ||
    `<p class="hint-msg">${t("noDownloadsYet")}</p>`;
}

function updateDownloadRow(entry) {
  const row = downloadsList.querySelector(`.video-card[data-id="${entry.id}"]`);
  if (!row) {
    renderDownloadsList();
    return;
  }
  const pct = entry.total ? Math.round((entry.received / entry.total) * 100) : 0;
  row.querySelector(".progress-track").classList.toggle("indeterminate", isIndeterminate(entry));
  row.querySelector(".progress-fill").style.width = `${pct}%`;
  row.querySelector(".progress-label").textContent = entry.statusText;
}

downloadsList.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-id]");
  if (!btn) return;
  const entry = downloads.get(Number(btn.dataset.id));
  if (!entry) return;
  if (btn.dataset.action === "cancel-dl") {
    entry.controller?.abort();
  } else if (btn.dataset.action === "retry-dl") {
    runDownload(entry);
  }
});

async function runDownload(entry) {
  entry.status = "starting";
  entry.statusText = t("waitingForServer");
  entry.controller = new AbortController();
  renderDownloadsList();

  const waitStart = performance.now();
  const tickInterval = setInterval(() => {
    if (entry.status !== "starting") return;
    const elapsed = Math.round((performance.now() - waitStart) / 1000);
    entry.statusText = t("stillWorking", elapsed);
    updateDownloadRow(entry);
  }, 1000);

  const params = new URLSearchParams({ url: entry.item.url, quality: entry.quality || "best", lang: getLang() });

  try {
    const res = await fetch(`/api/download?${params.toString()}`, { signal: entry.controller.signal });
    clearInterval(tickInterval);

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `${t("somethingWrong")} (${res.status})`);
    }

    entry.status = "downloading";
    entry.total = Number(res.headers.get("Content-Length")) || 0;
    const filename = extractFilename(res.headers.get("Content-Disposition")) || "video.mp4";

    const reader = res.body.getReader();
    const chunks = [];
    entry.received = 0;
    const startTime = performance.now();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      entry.received += value.length;

      const elapsed = (performance.now() - startTime) / 1000;
      const eta =
        elapsed > 0.5 && entry.total
          ? formatEta((entry.total - entry.received) / (entry.received / elapsed))
          : null;

      if (entry.total) {
        const pct = Math.round((entry.received / entry.total) * 100);
        entry.statusText = `${pct}% (${formatBytes(entry.received)} / ${formatBytes(entry.total)})${eta ? ` — ${eta}` : ""}`;
      } else {
        entry.statusText = formatBytes(entry.received);
      }
      updateDownloadRow(entry);
    }

    const blob = new Blob(chunks, { type: "video/mp4" });
    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);

    entry.status = "done";
    entry.statusText = t("done");
    renderDownloadsList();
  } catch (err) {
    clearInterval(tickInterval);
    if (err.name === "AbortError") {
      entry.status = "cancelled";
      entry.statusText = t("cancelled");
    } else {
      entry.status = "error";
      entry.statusText = err.message || t("somethingWrong");
    }
    renderDownloadsList();
  }
}

const DOWNLOAD_RATE_LIMIT = 10;
const DOWNLOAD_RATE_WINDOW_MS = 60000;

// Mirrors the server's per-IP rate limit on /api/download so a big batch
// paces itself instead of hitting 429s partway through.
async function waitForDownloadSlot(startTimes, entry) {
  const now = Date.now();
  while (startTimes.length && startTimes[0] <= now - DOWNLOAD_RATE_WINDOW_MS) {
    startTimes.shift();
  }
  if (startTimes.length >= DOWNLOAD_RATE_LIMIT) {
    const waitMs = startTimes[0] + DOWNLOAD_RATE_WINDOW_MS - now + 250;
    entry.status = "waiting";
    entry.statusText = t("queuedWaiting", Math.ceil(waitMs / 1000));
    renderDownloadsList();
    await new Promise((r) => setTimeout(r, waitMs));
    return waitForDownloadSlot(startTimes, entry);
  }
  startTimes.push(Date.now());
}

downloadAllBtn.addEventListener("click", async () => {
  const cards = [...resultsList.querySelectorAll(".video-card:not(.errored)")];
  const queued = [];
  for (const card of cards) {
    const index = Number(card.dataset.index);
    const item = currentItems[index];
    if (!item.selected) continue;
    const quality = card.querySelector(".quality-select")?.value;
    queued.push(createDownloadEntry(item, quality));
  }
  if (!queued.length) return;

  goToDownloads();
  const startTimes = [];
  for (const entry of queued) {
    await waitForDownloadSlot(startTimes, entry);
    await runDownload(entry);
  }
});

// If the visitor navigates away or closes the tab mid-download, abort every
// in-flight request instead of letting it keep streaming to a dead client.
window.addEventListener("pagehide", () => {
  downloads.forEach((entry) => entry.controller?.abort());
});

// ---------- Analyze / clear / validation ----------

analyzeBtn.addEventListener("click", async () => {
  globalError.classList.add("hidden");
  const urls = urlsEl.value
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);

  if (!urls.length) {
    globalError.textContent = t("pasteAtLeastOne");
    globalError.classList.remove("hidden");
    return;
  }

  setLoading(true);
  resultsSection.classList.add("hidden");

  try {
    const res = await fetch("/api/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls, lang: getLang() }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || t("unknownError"));
    }
    currentItems = (data.items || []).map((item) => ({ ...item, selected: true }));
    render();
    resultsSection.classList.remove("hidden");
  } catch (err) {
    globalError.textContent = err.message || t("somethingWrong");
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

function validateUrls() {
  const lines = urlsEl.value
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);

  if (!lines.length) {
    validationHint.classList.add("hidden");
    analyzeBtn.disabled = false;
    return;
  }

  const invalid = lines.filter((u) => !isLikelyYoutubeUrl(u));

  if (invalid.length === lines.length) {
    validationHint.textContent = t("noneLookValid");
    validationHint.classList.remove("hidden");
    analyzeBtn.disabled = true;
  } else if (invalid.length > 0) {
    validationHint.textContent = t("someInvalid", invalid.length, lines.length);
    validationHint.classList.remove("hidden");
    analyzeBtn.disabled = false;
  } else {
    validationHint.classList.add("hidden");
    analyzeBtn.disabled = false;
  }
}

urlsEl.addEventListener("input", validateUrls);

clearBtn.addEventListener("click", () => {
  urlsEl.value = "";
  currentItems = [];
  resultsList.innerHTML = "";
  resultsSection.classList.add("hidden");
  skeletonSection.classList.add("hidden");
  globalError.classList.add("hidden");
  validationHint.classList.add("hidden");
  analyzeBtn.disabled = false;
  urlsEl.focus();
});
