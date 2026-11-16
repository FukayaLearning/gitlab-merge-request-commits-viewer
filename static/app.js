const REVIEWED_STORAGE_KEY = "gitlab-mr-viewer:reviewed-commits";

const state = {
  repoInfo: null,
  mrs: [],
  base: "",
  head: "HEAD",
  commits: [],
  selectedSha: null,
  currentDiff: null,
  diffMode: "side-by-side",
  ignoreWhitespace: false,
  reviewedMap: loadReviewedMap(),
  commitsRequestSeq: 0,
  diffRequestSeq: 0,
  commitsAbortController: null,
  diffAbortController: null,
};

function parseReviewedMap(raw) {
  if (!raw) {
    return null;
  }
  const parsed = JSON.parse(raw);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
}

function loadReviewedMap() {
  try {
    return parseReviewedMap(window.localStorage.getItem(REVIEWED_STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

function saveReviewedMap() {
  try {
    window.localStorage.setItem(REVIEWED_STORAGE_KEY, JSON.stringify(state.reviewedMap));
  } catch {
    // Ignore storage quota or private mode errors
  }
}

function getReviewStorageKey(sha) {
  const repoPath = state.repoInfo?.repo_path || "";
  return repoPath ? `${repoPath}:${sha}` : sha;
}

function isCommitReviewed(sha) {
  if (!sha) {
    return false;
  }
  return Boolean(state.reviewedMap[getReviewStorageKey(sha)] || state.reviewedMap[sha]);
}

function getBadgeMeta(changeType) {
  if (changeType === "command") {
    return { label: "🤖 Command", className: "badge-command" };
  }
  if (changeType === "test") {
    return { label: "✅ Test", className: "badge-test" };
  }
  return { label: "✍️ Manual", className: "badge-manual" };
}

const els = {
  repoName: document.getElementById("repo-name"),
  currentBranch: document.getElementById("current-branch"),
  mrSelect: document.getElementById("mr-select"),
  mrStatus: document.getElementById("mr-status"),
  baseSelect: document.getElementById("base-branch-select"),
  headSelect: document.getElementById("head-branch-select"),
  reloadBtn: document.getElementById("reload-btn"),
  globalError: document.getElementById("global-error"),
  commitList: document.getElementById("commit-list"),
  reviewProgress: document.getElementById("review-progress"),
  commitSummary: document.getElementById("commit-summary"),
  diffFileCount: document.getElementById("diff-file-count"),
  changedFiles: document.getElementById("changed-files"),
  diffViewer: document.getElementById("diff-viewer"),
  modeSplitBtn: document.getElementById("mode-split-btn"),
  modeUnifiedBtn: document.getElementById("mode-unified-btn"),
  ignoreWhitespaceCheckbox: document.getElementById("ignore-whitespace-checkbox"),
};

function showError(message) {
  if (!message) {
    els.globalError.hidden = true;
    els.globalError.textContent = "";
    return;
  }
  els.globalError.textContent = message;
  els.globalError.hidden = false;
}

async function fetchJson(url, signal) {
  const response = await fetch(url, { cache: "no-store", signal });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `Request failed: ${response.status}`);
  }
  return data;
}

function populateBranchSelect(selectEl, branches, selectedValue) {
  selectEl.innerHTML = "";
  const options = [...branches];
  if (selectedValue && !options.includes(selectedValue)) {
    options.unshift(selectedValue);
  }
  for (const branch of options) {
    const opt = document.createElement("option");
    opt.value = branch;
    opt.textContent = branch;
    if (branch === selectedValue) {
      opt.selected = true;
    }
    selectEl.appendChild(opt);
  }
}

function populateMrSelect(mrs, fallback, reason) {
  els.mrSelect.innerHTML = "";
  const localOpt = document.createElement("option");
  localOpt.value = "";
  localOpt.textContent = "ローカルブランチ比較";
  els.mrSelect.appendChild(localOpt);

  for (const mr of mrs) {
    const opt = document.createElement("option");
    opt.value = String(mr.iid);
    opt.textContent = `!${mr.iid} ${mr.title} (${mr.target_branch} ← ${mr.source_branch})`;
    opt.dataset.base = mr.target_branch;
    opt.dataset.head = mr.source_branch;
    els.mrSelect.appendChild(opt);
  }

  if (fallback) {
    els.mrStatus.textContent = reason ? `Local mode (${reason})` : "Local mode";
    els.mrStatus.hidden = false;
  } else {
    els.mrStatus.hidden = true;
  }
}

function updateReviewProgress() {
  const total = state.commits.length;
  const reviewedCount = state.commits.filter((c) => isCommitReviewed(c.sha)).length;
  els.reviewProgress.textContent = `${reviewedCount} / ${total} Reviewed`;
}

function toggleReviewed(sha) {
  if (!sha) {
    return;
  }
  const key = getReviewStorageKey(sha);
  if (isCommitReviewed(sha)) {
    delete state.reviewedMap[key];
    delete state.reviewedMap[sha];
  } else {
    state.reviewedMap[key] = true;
  }
  saveReviewedMap();
  renderCommitList();
}

function renderCommitSummary(commit) {
  if (!commit) {
    els.commitSummary.innerHTML = '<p class="empty-state">表示するコミットがありません。</p>';
    return;
  }

  els.commitSummary.innerHTML = "";
  const badge = getBadgeMeta(commit.change_type);

  const header = document.createElement("div");
  header.className = "summary-header";

  const titleRow = document.createElement("div");
  titleRow.className = "summary-title-row";

  const title = document.createElement("h2");
  title.className = "summary-title";
  title.textContent = commit.subject;

  const badgeEl = document.createElement("span");
  badgeEl.className = `change-badge ${badge.className}`;
  badgeEl.textContent = badge.label;

  titleRow.append(title, badgeEl);

  const meta = document.createElement("div");
  meta.className = "summary-meta";
  meta.textContent = `SHA: ${commit.sha}  |  Author: ${commit.author}  |  Date: ${commit.date}`;

  header.append(titleRow, meta);
  els.commitSummary.appendChild(header);

  const trailers = commit.trailers || {};
  if (trailers.executed_command && trailers.executed_command.toLowerCase() !== "manual") {
    const cmdBox = document.createElement("div");
    cmdBox.className = "executed-command-box";

    const cmdLabel = document.createElement("div");
    cmdLabel.className = "executed-command-label";
    cmdLabel.textContent = "🤖 Executed-Command (Mechanical Change)";

    const cmdCode = document.createElement("code");
    cmdCode.className = "executed-command-code";
    cmdCode.textContent = trailers.executed_command;

    cmdBox.append(cmdLabel, cmdCode);
    els.commitSummary.appendChild(cmdBox);
  }

  const trailerRows = [
    ["Task", trailers.task],
    ["Why", trailers.why],
    ["What", trailers.what],
    ["Verification", trailers.verification],
    ["Issue", trailers.issue],
  ].filter(([, value]) => Boolean(value));

  if (trailerRows.length > 0) {
    const grid = document.createElement("div");
    grid.className = "trailer-grid";
    for (const [label, value] of trailerRows) {
      const k = document.createElement("div");
      k.className = "trailer-key";
      k.textContent = label;
      const v = document.createElement("div");
      v.className = "trailer-val";
      v.textContent = value;
      grid.append(k, v);
    }
    els.commitSummary.appendChild(grid);
  } else if (commit.body) {
    const bodyPre = document.createElement("pre");
    bodyPre.className = "commit-body-fallback";
    bodyPre.textContent = commit.body;
    els.commitSummary.appendChild(bodyPre);
  }
}

function scrollToFileDiff(filePath) {
  const d2hHeaders = els.diffViewer.querySelectorAll(".d2h-file-wrapper");
  for (const wrapper of d2hHeaders) {
    const nameEl = wrapper.querySelector(".d2h-file-name");
    const nameText = nameEl && nameEl.textContent ? nameEl.textContent.trim() : "";
    if (
      nameText === filePath ||
      nameText.endsWith(`/${filePath}`) ||
      nameText.endsWith(`→ ${filePath}`)
    ) {
      wrapper.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
  }
  const plainBlocks = els.diffViewer.querySelectorAll("[data-file-path]");
  for (const block of plainBlocks) {
    if (block.dataset.filePath === filePath) {
      block.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
  }
}

function renderChangedFiles(files) {
  els.changedFiles.innerHTML = "";
  els.diffFileCount.textContent = `${files.length} files`;
  for (const file of files) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "file-chip";

    const pathSpan = document.createElement("span");
    pathSpan.textContent = file.path;

    const addSpan = document.createElement("span");
    addSpan.className = "stat-add";
    addSpan.textContent = `+${file.additions}`;

    const delSpan = document.createElement("span");
    delSpan.className = "stat-del";
    delSpan.textContent = `-${file.deletions}`;

    chip.append(pathSpan, addSpan, delSpan);
    chip.addEventListener("click", () => scrollToFileDiff(file.path));
    els.changedFiles.appendChild(chip);
  }
}

function renderPlainDiffFallback(diffText) {
  els.diffViewer.innerHTML = "";
  const sections = diffText.split(/(?=^diff --git )/m).filter((s) => s.trim());
  for (const section of sections) {
    const lines = section.split("\n");
    const firstLine = lines[0] || "";
    const match = firstLine.match(/^diff --git a\/(.+?) b\/(.+)$/);
    const filePath = match ? match[2] : firstLine;

    const block = document.createElement("div");
    block.className = "plain-diff-file";
    block.dataset.filePath = filePath;

    const header = document.createElement("div");
    header.className = "plain-diff-header";
    header.textContent = filePath;

    const pre = document.createElement("pre");
    pre.className = "plain-diff-pre";
    for (const line of lines) {
      const lineEl = document.createElement("span");
      lineEl.className = "diff-line";
      if (line.startsWith("+") && !line.startsWith("+++")) {
        lineEl.classList.add("diff-line-add");
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        lineEl.classList.add("diff-line-del");
      } else if (line.startsWith("@@")) {
        lineEl.classList.add("diff-line-hunk");
      }
      lineEl.textContent = line;
      pre.appendChild(lineEl);
    }

    block.append(header, pre);
    els.diffViewer.appendChild(block);
  }
}

function renderDiff(diffText) {
  if (!diffText || !diffText.trim()) {
    els.diffViewer.innerHTML = '<p class="empty-state">表示する差分がありません。</p>';
    return;
  }

  if (typeof window.Diff2HtmlUI === "function") {
    els.diffViewer.innerHTML = "";
    const ui = new window.Diff2HtmlUI(els.diffViewer, diffText, {
      drawFileList: false,
      matching: "lines",
      outputFormat: state.diffMode,
      colorScheme: "dark",
      synchronisedScroll: true,
    });
    ui.draw();
    if (typeof ui.highlightCode === "function") {
      ui.highlightCode();
    }
    return;
  }

  renderPlainDiffFallback(diffText);
}

async function loadCommitDiff(sha) {
  if (!sha) {
    state.currentDiff = null;
    renderChangedFiles([]);
    renderDiff("");
    return;
  }

  if (state.diffAbortController) {
    state.diffAbortController.abort();
    state.diffAbortController = null;
  }

  const requestSeq = ++state.diffRequestSeq;
  const controller = new AbortController();
  state.diffAbortController = controller;

  try {
    const params = new URLSearchParams({
      ignore_whitespace: state.ignoreWhitespace ? "true" : "false",
    });
    const data = await fetchJson(
      `/api/commits/${encodeURIComponent(sha)}/diff?${params.toString()}`,
      controller.signal
    );
    if (requestSeq !== state.diffRequestSeq || state.selectedSha !== sha) {
      return;
    }
    state.currentDiff = data;
    renderChangedFiles(data.files || []);
    renderDiff(data.diff || "");
  } catch (err) {
    if (err && err.name === "AbortError") {
      return;
    }
    if (requestSeq === state.diffRequestSeq) {
      showError(err.message);
    }
  }
}

function selectCommit(sha) {
  state.selectedSha = sha;
  renderCommitList();
  const commit = state.commits.find((c) => c.sha === sha) || null;
  renderCommitSummary(commit);
  loadCommitDiff(sha);
}

function selectCommitByOffset(delta) {
  if (state.commits.length === 0) {
    return;
  }
  const currentIdx = state.commits.findIndex((c) => c.sha === state.selectedSha);
  const baseIdx = currentIdx === -1 ? 0 : currentIdx;
  const nextIdx = Math.max(0, Math.min(state.commits.length - 1, baseIdx + delta));
  const nextCommit = state.commits[nextIdx];
  if (nextCommit) {
    selectCommit(nextCommit.sha);
  }
}

function renderCommitList() {
  els.commitList.innerHTML = "";
  updateReviewProgress();

  if (state.commits.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "選択範囲にコミットがありません。";
    els.commitList.appendChild(empty);
    return;
  }

  for (const commit of state.commits) {
    const isSelected = commit.sha === state.selectedSha;
    const isReviewed = isCommitReviewed(commit.sha);
    const badge = getBadgeMeta(commit.change_type);

    const li = document.createElement("li");
    li.className = "commit-item";
    if (isSelected) {
      li.classList.add("selected");
    }
    if (isReviewed) {
      li.classList.add("reviewed");
    }
    li.setAttribute("role", "option");
    li.setAttribute("aria-selected", isSelected ? "true" : "false");

    const topRow = document.createElement("div");
    topRow.className = "commit-top-row";

    const badgesWrap = document.createElement("div");
    badgesWrap.className = "commit-badges";

    const badgeSpan = document.createElement("span");
    badgeSpan.className = `change-badge ${badge.className}`;
    badgeSpan.textContent = badge.label;
    badgesWrap.appendChild(badgeSpan);

    for (const taskId of commit.task_ids || []) {
      const taskSpan = document.createElement("span");
      taskSpan.className = "task-pill";
      taskSpan.textContent = taskId;
      badgesWrap.appendChild(taskSpan);
    }

    const reviewLabel = document.createElement("label");
    reviewLabel.className = "reviewed-toggle";
    reviewLabel.addEventListener("click", (e) => e.stopPropagation());

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = isReviewed;
    checkbox.setAttribute("aria-label", `Mark ${commit.short_sha} as reviewed`);
    checkbox.addEventListener("change", () => toggleReviewed(commit.sha));

    const reviewText = document.createElement("span");
    reviewText.textContent = "Reviewed";
    reviewLabel.append(checkbox, reviewText);

    topRow.append(badgesWrap, reviewLabel);

    const subjectEl = document.createElement("div");
    subjectEl.className = "commit-subject";
    subjectEl.textContent = commit.subject;

    const metaEl = document.createElement("div");
    metaEl.className = "commit-meta-line";
    const shaSpan = document.createElement("span");
    shaSpan.className = "commit-sha";
    shaSpan.textContent = commit.short_sha;
    const authorSpan = document.createElement("span");
    authorSpan.textContent = commit.author;
    metaEl.append(shaSpan, authorSpan);

    li.append(topRow, subjectEl, metaEl);
    li.addEventListener("click", () => selectCommit(commit.sha));
    els.commitList.appendChild(li);

    if (isSelected && typeof li.scrollIntoView === "function") {
      li.scrollIntoView({ block: "nearest" });
    }
  }
}

async function loadCommits() {
  if (!state.base || !state.head) {
    return;
  }
  if (state.commitsAbortController) {
    state.commitsAbortController.abort();
    state.commitsAbortController = null;
  }

  const requestSeq = ++state.commitsRequestSeq;
  const requestedBase = state.base;
  const requestedHead = state.head;
  const controller = new AbortController();
  state.commitsAbortController = controller;

  showError("");
  try {
    const params = new URLSearchParams({ base: requestedBase, head: requestedHead });
    const data = await fetchJson(`/api/commits?${params.toString()}`, controller.signal);
    if (
      requestSeq !== state.commitsRequestSeq ||
      state.base !== requestedBase ||
      state.head !== requestedHead
    ) {
      return;
    }
    state.commits = data.commits || [];
    state.selectedSha = state.commits.length > 0 ? state.commits[0].sha : null;
    renderCommitList();
    if (state.selectedSha) {
      selectCommit(state.selectedSha);
    } else {
      renderCommitSummary(null);
      loadCommitDiff(null);
    }
  } catch (err) {
    if (err && err.name === "AbortError") {
      return;
    }
    if (requestSeq === state.commitsRequestSeq) {
      showError(err.message);
    }
  }
}

async function init() {
  showError("");
  try {
    const [repoInfo, mrData] = await Promise.all([
      fetchJson("/api/repo-info"),
      fetchJson("/api/mrs"),
    ]);
    state.repoInfo = repoInfo;
    state.mrs = mrData.mrs || [];
    state.base = mrData.default_base || repoInfo.default_base || "main";
    state.head = mrData.default_head || repoInfo.current_branch || "HEAD";

    els.repoName.textContent = repoInfo.repo_name;
    els.currentBranch.textContent = repoInfo.current_branch;

    const branches = repoInfo.branches || [];
    populateBranchSelect(els.baseSelect, branches, state.base);
    populateBranchSelect(els.headSelect, ["HEAD", ...branches], state.head);
    populateMrSelect(state.mrs, mrData.fallback, mrData.reason);

    await loadCommits();
  } catch (err) {
    showError(err.message);
  }
}

els.mrSelect.addEventListener("change", () => {
  const selected = els.mrSelect.selectedOptions[0];
  if (selected && selected.value) {
    state.base = selected.dataset.base || state.base;
    state.head = selected.dataset.head || state.head;
    populateBranchSelect(els.baseSelect, state.repoInfo?.branches || [], state.base);
    populateBranchSelect(els.headSelect, ["HEAD", ...(state.repoInfo?.branches || [])], state.head);
  }
  loadCommits();
});

els.baseSelect.addEventListener("change", () => {
  els.mrSelect.value = "";
  state.base = els.baseSelect.value;
  loadCommits();
});

els.headSelect.addEventListener("change", () => {
  els.mrSelect.value = "";
  state.head = els.headSelect.value;
  loadCommits();
});

els.reloadBtn.addEventListener("click", () => {
  init();
});

function setDiffMode(mode) {
  state.diffMode = mode;
  els.modeSplitBtn.classList.toggle("active", mode === "side-by-side");
  els.modeUnifiedBtn.classList.toggle("active", mode === "line-by-line");
  if (state.currentDiff) {
    renderDiff(state.currentDiff.diff || "");
  }
}

els.modeSplitBtn.addEventListener("click", () => setDiffMode("side-by-side"));
els.modeUnifiedBtn.addEventListener("click", () => setDiffMode("line-by-line"));

els.ignoreWhitespaceCheckbox.addEventListener("change", () => {
  state.ignoreWhitespace = els.ignoreWhitespaceCheckbox.checked;
  if (state.selectedSha) {
    loadCommitDiff(state.selectedSha);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) {
    return;
  }
  const target = event.target;
  if (
    target &&
    (target.isContentEditable ||
      target.tagName === "SELECT" ||
      target.tagName === "TEXTAREA" ||
      (target.tagName === "INPUT" && target.type !== "checkbox"))
  ) {
    return;
  }

  if (event.key === "j" || event.key === "ArrowDown") {
    event.preventDefault();
    selectCommitByOffset(1);
  } else if (event.key === "k" || event.key === "ArrowUp") {
    event.preventDefault();
    selectCommitByOffset(-1);
  } else if (event.key === "r") {
    event.preventDefault();
    toggleReviewed(state.selectedSha);
  }
});

init();
