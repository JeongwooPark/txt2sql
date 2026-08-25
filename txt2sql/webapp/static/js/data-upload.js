(function () {
  const listEl = document.getElementById("dataset-list");
  const dropZone = document.getElementById("file-upload-area");
  const fileInput = document.getElementById("shapefile-input");
  const fileInfo = document.getElementById("file-info");
  const uploadBtn = document.getElementById("upload-btn");
  const statusList = document.getElementById("status-list");
  const progress = document.getElementById("upload-progress");
  let selectedFile = null;
  let busy = false;

  function addStatus(message, kind) {
    if (!statusList) return;
    const item = document.createElement("div");
    item.className = `status-item ${kind || ""}`;
    item.textContent = `${new Date().toLocaleTimeString()} · ${message}`;
    statusList.prepend(item);
  }

  async function refreshTables() {
    if (!listEl) return;
    listEl.innerHTML = '<p class="layer-empty">불러오는 중…</p>';
    try {
      const tables = await loadSpatialTables();
      renderTableList(listEl, tables, (table) => {
        window.location.href = `/data/metadata?table=${encodeURIComponent(table.full_name)}`;
      });
    } catch (err) {
      listEl.innerHTML = `<p class="layer-empty">${escapeHtml(err.message)}</p>`;
    }
  }

  function processFile(file) {
    if (!file || !file.name.toLowerCase().endsWith(".zip")) {
      addStatus("Shapefile ZIP 파일만 업로드할 수 있습니다.", "err");
      return;
    }
    selectedFile = file;
    document.getElementById("file-name").textContent = file.name;
    document.getElementById("file-size").textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
    document.getElementById("table-name").textContent = file.name.replace(/\.zip$/i, "");
    fileInfo.hidden = false;
    uploadBtn.disabled = false;
    addStatus(`파일 "${file.name}"이 선택되었습니다.`, "ok");
  }

  dropZone?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) processFile(file);
  });
  dropZone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone?.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone?.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    if (file) processFile(file);
  });

  uploadBtn?.addEventListener("click", async () => {
    if (!selectedFile || busy) return;
    busy = true;
    uploadBtn.disabled = true;
    uploadBtn.textContent = "업로드 중…";
    progress?.classList.add("on");
    addStatus("업로드를 시작합니다…", "");
    const form = new FormData();
    form.append("shapefile", selectedFile);
    try {
      const data = await dataJson("/api/data/upload", { method: "POST", body: form });
      addStatus(data.message || "업로드 완료", "ok");
      if (data.wired && data.wired.d198_coverage) {
        const gus = Object.keys(data.wired.d198_coverage);
        if (gus.length) {
          addStatus("질의 연결 구: " + gus.join(" · "), "ok");
        }
      }
      selectedFile = null;
      fileInput.value = "";
      fileInfo.hidden = true;
      await refreshTables();
    } catch (err) {
      addStatus(err.message, "err");
    } finally {
      busy = false;
      uploadBtn.disabled = false;
      uploadBtn.textContent = "PostgreSQL에 업로드";
      progress?.classList.remove("on");
    }
  });

  refreshTables();
})();
