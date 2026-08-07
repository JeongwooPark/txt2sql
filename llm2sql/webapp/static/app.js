(() => {
  const messagesEl = document.getElementById("messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("question");
  const sendBtn = document.getElementById("send");
  const newChatBtn = document.getElementById("new-chat");
  const suggestions = document.getElementById("suggestions");

  const SESSION_KEY = "llm2sql_session_id";
  let sessionId = localStorage.getItem(SESSION_KEY) || null;
  let busy = false;
  let stickToBottom = true;
  let scrollRaf = 0;

  function isNearBottom(threshold = 80) {
    const gap =
      messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight;
    return gap <= threshold;
  }

  function scrollToBottom(force = false) {
    if (!force && !stickToBottom) return;
    if (scrollRaf) cancelAnimationFrame(scrollRaf);
    const pin = () => {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    };
    scrollRaf = requestAnimationFrame(() => {
      scrollRaf = 0;
      pin();
      // 스트리밍·메타/SQL 블록 추가로 높이가 늘어난 뒤 한 번 더
      requestAnimationFrame(pin);
    });
  }

  messagesEl.addEventListener(
    "scroll",
    () => {
      stickToBottom = isNearBottom();
    },
    { passive: true }
  );

  function clearWelcome() {
    const welcome = messagesEl.querySelector(".welcome");
    if (welcome) welcome.remove();
  }

  function appendUser(text) {
    clearWelcome();
    stickToBottom = true;
    const row = document.createElement("div");
    row.className = "row user";
    row.innerHTML = `<div class="bubble"></div>`;
    row.querySelector(".bubble").textContent = text;
    messagesEl.appendChild(row);
    scrollToBottom(true);
  }

  function appendBotShell() {
    clearWelcome();
    stickToBottom = true;
    const row = document.createElement("div");
    row.className = "row bot";
    row.innerHTML = `
      <div class="avatar">AI</div>
      <div class="bubble">
        <div class="status">
          <span class="spinner" aria-hidden="true"></span>
          <span class="status-text">질문 분석 중…</span>
        </div>
        <div class="answer" hidden></div>
        <div class="meta" hidden></div>
        <pre class="sql-block" hidden></pre>
      </div>
    `;
    messagesEl.appendChild(row);
    scrollToBottom(true);
    return {
      row,
      bubble: row.querySelector(".bubble"),
      status: row.querySelector(".status"),
      statusText: row.querySelector(".status-text"),
      answer: row.querySelector(".answer"),
      meta: row.querySelector(".meta"),
      sql: row.querySelector(".sql-block"),
    };
  }

  function setBusy(next) {
    busy = next;
    sendBtn.disabled = next;
    input.disabled = next;
  }

  function stageLabel(stage, message) {
    const map = {
      start: "질문 수신",
      route: "의도 분석",
      schema: "스키마 검색",
      llm: "SQL 생성",
      sql: "SQL 준비",
      validate: "검증",
      execute: "DB 조회",
      result: "결과 정리",
      answer: "답변 작성",
      clarify: "확인 필요",
      meta: "메타 설명",
      profile: "특징 요약",
      error: "오류 처리",
    };
    return message || map[stage] || stage;
  }

  async function ensureSession() {
    if (sessionId) return sessionId;
    const res = await fetch("/api/session", { method: "POST" });
    if (!res.ok) throw new Error("세션을 만들 수 없습니다.");
    const data = await res.json();
    sessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);
    return sessionId;
  }

  async function sendQuestion(question) {
    const q = question.trim();
    if (!q || busy) return;

    setBusy(true);
    appendUser(q);
    input.value = "";
    autoResize();

    const shell = appendBotShell();

    try {
      await ensureSession();
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, session_id: sessionId }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`요청 실패 (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      const state = {
        startedAnswer: false,
        streamed: "",
        finished: false,
      };

      const ingest = (chunk) => {
        buffer += chunk;
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          let evt;
          try {
            evt = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          handleEvent(evt, shell, state);
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (value) ingest(decoder.decode(value, { stream: true }));
        if (done) {
          ingest(decoder.decode());
          if (buffer.trim()) ingest(`${buffer}\n\n`);
          break;
        }
      }

      if (!state.finished) {
        finishBot(shell, state.streamed || "(응답이 중간에 끊겼습니다.)");
      }
    } catch (err) {
      finishBot(
        shell,
        err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.",
        { error: true }
      );
    } finally {
      hideLoading(shell);
      setBusy(false);
      input.focus();
      scrollToBottom(true);
    }
  }

  function hideLoading(shell) {
    if (!shell?.status) return;
    shell.status.hidden = true;
    shell.status.style.display = "none";
    const spinner = shell.status.querySelector(".spinner");
    if (spinner) spinner.remove();
    const cursor = shell.answer?.querySelector(".cursor");
    if (cursor) cursor.remove();
  }

  function finishBot(shell, text, { error = false } = {}) {
    hideLoading(shell);
    shell.answer.hidden = false;
    shell.answer.textContent = text;
    if (error) shell.bubble.classList.add("error");
  }

  function handleEvent(evt, shell, state) {
    if (evt.type === "ready" && evt.session_id) {
      sessionId = evt.session_id;
      localStorage.setItem(SESSION_KEY, sessionId);
      return;
    }

    if (evt.type === "progress") {
      if (!state.startedAnswer && !state.finished) {
        shell.statusText.textContent = stageLabel(evt.stage, evt.message);
      }
      return;
    }

    if (evt.type === "token") {
      if (state.finished) return;
      if (!state.startedAnswer) {
        state.startedAnswer = true;
        hideLoading(shell);
        shell.answer.hidden = false;
        shell.answer.textContent = "";
        const cursor = document.createElement("span");
        cursor.className = "cursor";
        shell.answer.appendChild(document.createTextNode(""));
        shell.answer.appendChild(cursor);
      }
      state.streamed += evt.text || "";
      const cursor = shell.answer.querySelector(".cursor");
      if (shell.answer.firstChild) {
        shell.answer.firstChild.textContent = state.streamed;
      }
      if (cursor) shell.answer.appendChild(cursor);
      scrollToBottom();
      return;
    }

    if (evt.type === "done") {
      state.finished = true;
      if (evt.session_id) {
        sessionId = evt.session_id;
        localStorage.setItem(SESSION_KEY, sessionId);
      }
      const result = evt.result || {};
      const finalAnswer = result.answer || state.streamed || "(답변 없음)";

      finishBot(shell, finalAnswer, { error: !result.ok });

      const chips = [];
      if (result.route) chips.push(`route: ${result.route}`);
      if (result.row_count != null) chips.push(`rows: ${result.row_count}`);
      if (Array.isArray(result.tables) && result.tables.length) {
        chips.push(`tables: ${result.tables.slice(0, 3).join(", ")}`);
      }
      if (chips.length) {
        shell.meta.hidden = false;
        shell.meta.innerHTML = chips
          .map((c) => `<span class="chip">${escapeHtml(c)}</span>`)
          .join("");
      }
      if (result.sql) {
        shell.sql.hidden = false;
        shell.sql.textContent = result.sql;
      }

      if (
        result.route === "clarify_place" &&
        Array.isArray(result.rows) &&
        result.rows.length > 0
      ) {
        const choices = document.createElement("div");
        choices.className = "choices";
        result.rows.forEach((opt, i) => {
          const n = i + 1;
          const place = opt.place || opt.A4 || `${n}번`;
          const count =
            opt.n != null ? ` · 건물 ${Number(opt.n).toLocaleString("ko-KR")}동` : "";
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "choice-btn";
          btn.dataset.q = String(n);
          btn.innerHTML = `<span class="choice-num">${n}</span><span class="choice-label">${escapeHtml(
            String(place)
          )}${escapeHtml(count)}</span>`;
          choices.appendChild(btn);
        });
        shell.bubble.appendChild(choices);
      }

      scrollToBottom(true);
      return;
    }

    if (evt.type === "error") {
      state.finished = true;
      finishBot(shell, evt.message || "오류가 발생했습니다.", { error: true });
      scrollToBottom(true);
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function autoResize() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    sendQuestion(input.value);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuestion(input.value);
    }
  });

  input.addEventListener("input", autoResize);

  suggestions?.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-q]");
    if (!btn) return;
    sendQuestion(btn.getAttribute("data-q") || "");
  });

  messagesEl.addEventListener("click", (e) => {
    const btn = e.target.closest("button.choice-btn[data-q]");
    if (!btn || busy) return;
    sendQuestion(btn.getAttribute("data-q") || "");
  });

  newChatBtn.addEventListener("click", async () => {
    localStorage.removeItem(SESSION_KEY);
    sessionId = null;
    messagesEl.innerHTML = `
      <div class="welcome">
        <h2>무엇을 찾아볼까요?</h2>
        <p>
          건물 건수·순위·특징, 메타데이터 설명, 후속 질문까지 대화로
          이어집니다.
        </p>
        <div class="suggestions" id="suggestions">
          <button type="button" data-q="기능 알려줘">기능 알려줘</button>
          <button type="button" data-q="해운대구 건물 몇 채야?">
            해운대구 건물 몇 채야?
          </button>
          <button type="button" data-q="구서동에서 건물면적이 가장 큰 아파트는?">
            구서동에서 건물면적이 가장 큰 아파트는?
          </button>
          <button type="button" data-q="구서동 아파트의 특징은?">
            구서동 아파트의 특징은?
          </button>
        </div>
      </div>
    `;
    document.getElementById("suggestions")?.addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-q]");
      if (!btn) return;
      sendQuestion(btn.getAttribute("data-q") || "");
    });
    try {
      await ensureSession();
    } catch {
      /* ignore */
    }
    input.focus();
  });

  input.focus();
})();
