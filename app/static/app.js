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
const selectAllCheckbox = document.getElementById("selectAllCheckbox");

let currentItems = [];
const activeDownloads = new Map();

function setLoading(isLoading) {
  analyzeBtn.disabled = isLoading;
  analyzeBtn.querySelector(".btn-label").textContent = isLoading ? "Analyzing..." : "Analyze";
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
  if (seconds < 1) return "almost done";
  if (seconds < 60) return `${Math.round(seconds)}s left`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s left`;
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

function qualityOptions(item) {
  const qualities = item.qualities && item.qualities.length ? item.qualities : ["best"];
  const preferred = qualities.includes("1080p") ? "1080p" : qualities[0];
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
      <div class="video-card-row">
        <input type="checkbox" class="video-checkbox" ${item.selected ? "checked" : ""} aria-label="Select this video" />
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
      </div>
      <div class="progress-track hidden">
        <div class="progress-fill"></div>
      </div>
      <p class="progress-label hidden"></p>
    </div>`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
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
  downloadAllBtn.textContent = `Download selected (${selectedCount})`;
  downloadAllBtn.disabled = selectedCount === 0;
}

function render() {
  resultsList.innerHTML = currentItems.map(renderItem).join("");
  const downloadable = selectableItems().length;
  resultsTitle.textContent = `Results (${currentItems.length})`;
  downloadAllBtn.classList.toggle("hidden", downloadable < 2);
  syncSelectAllCheckbox();
  syncDownloadAllLabel();
}

function extractFilename(contentDisposition) {
  if (!contentDisposition) return null;
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) return decodeURIComponent(utf8Match[1]);
  const asciiMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return asciiMatch ? asciiMatch[1] : null;
}

async function triggerDownload(item, quality, card, index) {
  const btn = card.querySelector(".dl-btn");
  const track = card.querySelector(".progress-track");
  const fill = card.querySelector(".progress-fill");
  const label = card.querySelector(".progress-label");

  const controller = new AbortController();
  activeDownloads.set(index, controller);

  btn.disabled = false;
  btn.textContent = "Cancel";
  btn.dataset.action = "cancel";
  track.classList.remove("hidden", "error");
  label.classList.remove("hidden");
  fill.style.width = "0%";
  label.textContent = "Starting...";

  const params = new URLSearchParams({ url: item.url, quality: quality || "best" });

  try {
    const res = await fetch(`/api/download?${params.toString()}`, { signal: controller.signal });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Download failed (${res.status})`);
    }

    const total = Number(res.headers.get("Content-Length")) || 0;
    const filename = extractFilename(res.headers.get("Content-Disposition")) || "video.mp4";

    const reader = res.body.getReader();
    const chunks = [];
    let received = 0;
    const startTime = performance.now();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.length;

      const elapsed = (performance.now() - startTime) / 1000;
      const eta = elapsed > 0.5 && total ? formatEta((total - received) / (received / elapsed)) : null;

      if (total) {
        const pct = Math.round((received / total) * 100);
        fill.style.width = `${pct}%`;
        label.textContent = `${pct}% (${formatBytes(received)} / ${formatBytes(total)})${eta ? ` — ${eta}` : ""}`;
      } else {
        label.textContent = formatBytes(received);
      }
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

    fill.style.width = "100%";
    label.textContent = "Done ✓";
    btn.textContent = "Started ✓";
    btn.dataset.action = "done";
    btn.disabled = true;
    btn.classList.add("done");
  } catch (err) {
    if (err.name === "AbortError") {
      label.textContent = "Cancelled";
      fill.style.width = "0%";
    } else {
      label.textContent = err.message || "Download failed.";
      track.classList.add("error");
    }
    btn.textContent = "Retry";
    btn.dataset.action = "download";
    btn.disabled = false;
  } finally {
    activeDownloads.delete(index);
  }
}

resultsList.addEventListener("click", (e) => {
  const cancelBtn = e.target.closest('[data-action="cancel"]');
  if (cancelBtn) {
    const card = cancelBtn.closest(".video-card");
    const index = Number(card.dataset.index);
    activeDownloads.get(index)?.abort();
    return;
  }

  const btn = e.target.closest('[data-action="download"]');
  if (!btn) return;
  const card = btn.closest(".video-card");
  const index = Number(card.dataset.index);
  const item = currentItems[index];
  const quality = card.querySelector(".quality-select")?.value;
  triggerDownload(item, quality, card, index);
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

downloadAllBtn.addEventListener("click", async () => {
  const cards = [...resultsList.querySelectorAll(".video-card:not(.errored)")];
  for (const card of cards) {
    const index = Number(card.dataset.index);
    const item = currentItems[index];
    if (!item.selected) continue;
    const quality = card.querySelector(".quality-select")?.value;
    await triggerDownload(item, quality, card, index);
  }
});

// If the visitor navigates away or closes the tab mid-download, abort every
// in-flight request instead of letting it keep streaming to a dead client.
window.addEventListener("pagehide", () => {
  activeDownloads.forEach((controller) => controller.abort());
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
    currentItems = (data.items || []).map((item) => ({ ...item, selected: true }));
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
    validationHint.textContent = "None of these look like YouTube links — check them before analyzing.";
    validationHint.classList.remove("hidden");
    analyzeBtn.disabled = true;
  } else if (invalid.length > 0) {
    validationHint.textContent = `${invalid.length} of ${lines.length} link(s) don't look like YouTube links and will likely fail.`;
    validationHint.classList.remove("hidden");
    analyzeBtn.disabled = false;
  } else {
    validationHint.classList.add("hidden");
    analyzeBtn.disabled = false;
  }
}

urlsEl.addEventListener("input", validateUrls);

clearBtn.addEventListener("click", () => {
  activeDownloads.forEach((controller) => controller.abort());
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
