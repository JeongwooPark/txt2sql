(function () {
  const listEl = document.getElementById("dataset-list");
  const emptyEl = document.getElementById("no-table-selected");
  const formEl = document.getElementById("metadata-form");
  const banner = document.getElementById("status-banner");
  const titleEl = document.getElementById("selected-table-title");
  const displayEl = document.getElementById("table-display-name");
  const categoryEl = document.getElementById("table-category");
  const descEl = document.getElementById("table-description");
  const commentsEl = document.getElementById("database-comments");
  const columnList = document.getElementById("column-list");
  let tables = [];
  let selected = null;
  let structure = [];
  let existing = null;
  let pendingRename = null;

  function showBanner(message, kind) {
    banner.textContent = message;
    banner.className = `status-banner on ${kind || "info"}`;
  }

  function hideForm() {
    emptyEl.hidden = false;
    formEl.hidden = true;
  }

  async function refreshTables(selectName) {
    listEl.innerHTML = '<p class="layer-empty">불러오는 중…</p>';
    try {
      tables = await loadSpatialTables();
      renderTableList(listEl, tables, selectTable);
      const wanted = selectName || new URLSearchParams(location.search).get("table");
      if (wanted) {
        const match = tables.find((item) => item.full_name === wanted || item.table_name === wanted);
        if (match) {
          const node = listEl.querySelector(`[data-full-name="${CSS.escape(match.full_name)}"]`);
          node?.classList.add("active");
          await selectTable(match);
        }
      }
    } catch (err) {
      listEl.innerHTML = `<p class="layer-empty">${escapeHtml(err.message)}</p>`;
    }
  }

  async function selectTable(table) {
    selected = table;
    pendingRename = null;
    titleEl.textContent = `테이블 메타데이터 — ${table.display_name} (${table.full_name})`;
    emptyEl.hidden = true;
    formEl.hidden = false;
    showBanner("테이블 정보를 불러오는 중…", "info");
    try {
      const [structRes, metaRes] = await Promise.all([
        dataJson(`/api/data/tables/${encodeURIComponent(table.full_name)}/structure`),
        dataJson(`/api/data/tables/${encodeURIComponent(table.full_name)}/metadata`),
      ]);
      structure = structRes.structure || [];
      existing = metaRes.metadata || {};
      existing.database_comments = metaRes.database_comments || {};
      fillForm();
      showBanner("테이블을 불러왔습니다.", "ok");
    } catch (err) {
      showBanner(err.message, "err");
    }
  }

  function fillForm() {
    const tableMeta = existing.table_metadata || {};
    displayEl.value = tableMeta.display_name || selected.table_name;
    categoryEl.value = tableMeta.category || "";
    descEl.value = tableMeta.description || existing.database_comments?.table_comment || "";
    const comments = existing.database_comments || {};
    const lines = [];
    if (comments.table_comment) lines.push(`테이블 주석: ${comments.table_comment}`);
    Object.entries(comments.column_comments || {}).forEach(([name, text]) => {
      lines.push(`${name}: ${text}`);
    });
    commentsEl.hidden = lines.length === 0;
    commentsEl.innerHTML = lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("");
    renderColumns();
  }

  function renderColumns() {
    columnList.innerHTML = "";
    const colMeta = existing.column_metadata || {};
    const colComments = existing.database_comments?.column_comments || {};
    structure.forEach((column) => {
      const name = column.column_name || "";
      const dtype = column.data_type || "";
      if (["geometry", "geom", "the_geom", "shape", "geography"].includes(name.toLowerCase())) return;
      if (["geometry", "geography", "raster"].includes(String(dtype).toLowerCase())) return;
      const meta = colMeta[name] || {};
      const description = meta.description || colComments[name] || "";
      const wrap = document.createElement("div");
      wrap.className = "column-item";
      wrap.innerHTML = `
        <div class="column-head">
          <strong>${escapeHtml(name)}</strong>
          <span class="dtype">${escapeHtml(dtype)}</span>
        </div>
        <div class="form-grid">
          <label>컬럼 표시명
            <input class="column-display-name" data-column="${escapeHtml(name)}" value="${escapeHtml(meta.display_name || "")}" />
          </label>
          <label>단위
            <input class="column-unit" data-column="${escapeHtml(name)}" value="${escapeHtml(meta.unit || "")}" />
          </label>
        </div>
        <label>컬럼 설명
          <textarea class="column-description" data-column="${escapeHtml(name)}" rows="2">${escapeHtml(description)}</textarea>
        </label>`;
      columnList.appendChild(wrap);
    });
    if (!columnList.children.length) {
      columnList.innerHTML = '<p class="layer-empty">편집할 컬럼이 없습니다.</p>';
    }
  }

  function collectPayload() {
    const column_metadata = {};
    structure.forEach((column) => {
      const name = column.column_name;
      const display = document.querySelector(`[data-column="${CSS.escape(name)}"].column-display-name`);
      const unit = document.querySelector(`[data-column="${CSS.escape(name)}"].column-unit`);
      const desc = document.querySelector(`[data-column="${CSS.escape(name)}"].column-description`);
      if (!display) return;
      column_metadata[name] = {
        display_name: display.value,
        unit: unit ? unit.value : "",
        description: desc ? desc.value : "",
        data_type: column.data_type,
      };
    });
    return {
      table_name: selected.full_name,
      table_metadata: {
        display_name: displayEl.value,
        description: descEl.value,
        category: categoryEl.value,
      },
      column_metadata,
      new_table_name: pendingRename || null,
    };
  }

  document.getElementById("rename-table-btn")?.addEventListener("click", () => {
    const name = displayEl.value.trim();
    if (!name) {
      showBanner("테이블 표시명을 먼저 입력하세요.", "err");
      return;
    }
    if (!confirm(`실제 테이블명을 "${name}"으로 바꾸겠습니까? GeoServer 레이어명은 그대로입니다.`)) return;
    pendingRename = name;
    showBanner("테이블명 변경이 준비되었습니다. 데이터 갱신을 누르세요.", "info");
  });

  document.getElementById("save-metadata-btn")?.addEventListener("click", async () => {
    if (!selected) return;
    const btn = document.getElementById("save-metadata-btn");
    btn.disabled = true;
    showBanner("데이터를 갱신하는 중…", "info");
    try {
      const data = await dataJson("/api/data/metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collectPayload()),
      });
      showBanner(data.message || "저장했습니다.", "ok");
      pendingRename = null;
      if (data.new_table_name) {
        await refreshTables(data.new_table_name);
      } else {
        await selectTable(selected);
      }
    } catch (err) {
      showBanner(err.message, "err");
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("reset-metadata-btn")?.addEventListener("click", () => {
    if (selected) {
      pendingRename = null;
      fillForm();
      showBanner("폼을 초기화했습니다.", "ok");
    }
  });

  document.getElementById("parse-code-btn")?.addEventListener("click", async () => {
    if (!selected) return;
    showBanner("테이블 코드를 해석하는 중…", "info");
    try {
      const data = await dataJson(
        `/api/data/tables/${encodeURIComponent(selected.full_name)}/parse`
      );
      const parsed = data.parsed_metadata || {};
      displayEl.value = parsed.display_name || displayEl.value;
      descEl.value = parsed.description || descEl.value;
      if (!categoryEl.value) categoryEl.value = "기타";
      existing = existing || {};
      existing.column_metadata = {
        ...(existing.column_metadata || {}),
        ...(parsed.column_metadata || {}),
      };
      renderColumns();
      showBanner(`해석 완료: ${parsed.display_name || selected.table_name}`, "ok");
    } catch (err) {
      showBanner(err.message, "err");
    }
  });

  hideForm();
  refreshTables();
})();
