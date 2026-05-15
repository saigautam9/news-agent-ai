/* Deep Signal — front-end app */
"use strict";

// ---------------------------------------------------------------- constants
const SEVERITY = {
  CRITICAL: { color: "#ef4444", dot: "🔴" },
  HIGH: { color: "#f59e0b", dot: "🟠" },
  MEDIUM: { color: "#eab308", dot: "🟡" },
  LOW: { color: "#64748b", dot: "⚪" },
};

const SIGNAL_COLOR = {
  bullish: "#22c55e",
  bearish: "#ef4444",
  tension: "#f59e0b",
  watch: "#38bdf8",
};

const DOMAIN_EMOJI = {
  Geopolitics: "🌍",
  Markets: "📈",
  Technology: "💻",
  Health: "🧬",
  Climate: "🌱",
  Society: "👥",
  Breaking: "🚨",
};
const DOMAIN_ORDER = ["Geopolitics", "Markets", "Technology", "Health", "Climate", "Society"];

// ---------------------------------------------------------------- helpers
const $ = (id) => document.getElementById(id);

function esc(text) {
  const d = document.createElement("div");
  d.textContent = text == null ? "" : String(text);
  return d.innerHTML;
}

async function getJson(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(data && data.error ? data.error : `Request failed (${res.status})`);
  return data;
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data && data.error ? data.error : `Request failed (${res.status})`);
  return data;
}

// ---------------------------------------------------------------- state
let busy = false;
const history = [];
const details = {}; // story id -> { deep, agents, synthesis, sources }

// ---------------------------------------------------------------- fetching
async function runStories(label, url, body) {
  if (busy) return;
  busy = true;
  setBusy(true);
  $("error").classList.add("hidden");
  $("status").classList.remove("hidden");
  $("status").innerHTML = `<span class="spinner"></span> Agents working — fetch → classify → rewrite…`;

  try {
    const data = body ? await postJson(url, body) : await getJson(url);
    const rs = { key: String(Date.now()), label, stories: data.stories || [], sources: data.sources || [] };
    history.unshift(rs);
    while (history.length > 8) history.pop();
    renderHistory(rs.key);
    renderResults(rs);
  } catch (e) {
    $("results").innerHTML = "";
    $("empty").classList.remove("hidden");
    $("error").textContent = e.message || "Something went wrong.";
    $("error").classList.remove("hidden");
  } finally {
    busy = false;
    setBusy(false);
    $("status").classList.add("hidden");
  }
}

function setBusy(on) {
  document.querySelectorAll("button").forEach((b) => {
    if (!b.classList.contains("chat-toggle") && !b.classList.contains("chat-close")) b.disabled = on;
  });
}

const loadToday = () => runStories("Today's Briefing", "/api/news");
const searchTopic = (q) => {
  const term = (q || "").trim();
  if (term) runStories(`“${term}”`, "/api/search", { query: term });
};

// ---------------------------------------------------------------- rendering
function renderHistory(activeKey) {
  const box = $("history");
  if (history.length < 2) {
    box.classList.add("hidden");
    return;
  }
  box.classList.remove("hidden");
  box.innerHTML = `<span class="history-label">Session</span>`;
  history.forEach((h) => {
    const b = document.createElement("button");
    b.className = "history-item" + (h.key === activeKey ? " active" : "");
    b.textContent = h.label;
    b.onclick = () => {
      renderHistory(h.key);
      renderResults(h);
    };
    box.appendChild(b);
  });
}

function renderResults(rs) {
  $("empty").classList.add("hidden");
  const root = $("results");
  root.innerHTML = "";

  if (!rs.stories.length) {
    root.innerHTML = `<p class="muted">No stories came back — try again.</p>`;
    return;
  }

  const head = document.createElement("div");
  head.className = "results-head";
  head.textContent = `${rs.label} — ${rs.stories.length} stories`;
  root.appendChild(head);

  // Group stories by domain into desk sections.
  const groups = {};
  rs.stories.forEach((s) => {
    const d = s.domain || "Other";
    (groups[d] = groups[d] || []).push(s);
  });
  const domains = Object.keys(groups).sort(
    (a, b) => (DOMAIN_ORDER.indexOf(a) + 99) % 100 - ((DOMAIN_ORDER.indexOf(b) + 99) % 100)
  );

  domains.forEach((domain) => {
    const section = document.createElement("div");
    section.className = "cat-section";
    const heading = document.createElement("div");
    heading.className = "cat-heading";
    heading.innerHTML =
      `<span>${DOMAIN_EMOJI[domain] || "📰"} ${esc(domain)}</span>` +
      `<span class="rule"></span>` +
      `<span class="count">${groups[domain].length}</span>`;
    section.appendChild(heading);
    groups[domain].forEach((s) => section.appendChild(storyCard(s)));
    root.appendChild(section);
  });

  if (rs.sources && rs.sources.length) root.appendChild(sourceList(rs.sources, "Fetched from"));
}

function storyCard(story) {
  const sev = SEVERITY[story.severity] || SEVERITY.MEDIUM;
  const card = document.createElement("article");
  card.className = "card";
  card.innerHTML = `
    <div class="meta">
      <span class="badge" style="color:${sev.color};border:1px solid ${sev.color}55">
        ${sev.dot} ${esc(story.severity)}
      </span>
      <span class="tag">${esc(story.domain)}</span>
      <span class="tag faint">urgency ${esc(story.urgency)}/10</span>
    </div>
    <h3>${esc(story.headline)}</h3>
    <p class="summary">${esc(story.summary)}</p>
    <p class="why">Why it matters: ${esc(story.why)}</p>
    <div class="actions">
      <button class="act" data-act="deep">▸ Deep Dive</button>
      <button class="act" data-act="agents">▸ Multi-Agent View</button>
    </div>
    <div class="panel-host"></div>`;

  const host = card.querySelector(".panel-host");
  const deepBtn = card.querySelector('[data-act="deep"]');
  const agentsBtn = card.querySelector('[data-act="agents"]');

  deepBtn.onclick = () => togglePanel(story, host, deepBtn, agentsBtn, "deep");
  agentsBtn.onclick = () => togglePanel(story, host, agentsBtn, deepBtn, "agents");
  return card;
}

async function togglePanel(story, host, btn, otherBtn, kind) {
  // Collapse if already open with this kind.
  if (host.dataset.kind === kind && host.innerHTML) {
    host.innerHTML = "";
    host.dataset.kind = "";
    btn.classList.remove("active");
    return;
  }
  otherBtn.classList.remove("active");
  btn.classList.add("active");
  host.dataset.kind = kind;

  const cache = details[story.id] || {};
  if ((kind === "deep" && cache.deep) || (kind === "agents" && cache.agents)) {
    host.innerHTML = kind === "deep" ? deepPanel(cache.deep, cache.deepSources) : agentsPanel(cache);
    return;
  }

  host.innerHTML = `<p class="status" style="margin-top:13px">
    <span class="spinner"></span> ${kind === "deep"
      ? "Investigating — causes, dots, narratives, history…"
      : "Five analysts debating this story…"}</p>`;

  try {
    const payload = { story: { headline: story.headline, summary: story.summary } };
    if (kind === "deep") {
      const data = await postJson("/api/analyze", payload);
      details[story.id] = { ...cache, deep: data.analysis, deepSources: data.sources };
      host.innerHTML = deepPanel(data.analysis, data.sources);
    } else {
      const data = await postJson("/api/agents", payload);
      details[story.id] = { ...cache, agents: data.agents, synthesis: data.synthesis, agentSources: data.sources };
      host.innerHTML = agentsPanel(details[story.id]);
    }
  } catch (e) {
    host.innerHTML = `<p class="error" style="margin-top:13px">${esc(e.message)}</p>`;
  }
}

// ---------------------------------------------------------------- panels
function row(k, v) {
  return v ? `<p class="kv"><b>${esc(k)}:</b> ${esc(v)}</p>` : "";
}
function section(title, inner) {
  return `<div class="section"><h4>${esc(title)}</h4>${inner}</div>`;
}
function list(items, bullet, color) {
  return `<ul class="list">${(items || [])
    .map((it) => `<li><span style="color:${color}">${bullet}</span> ${esc(it)}</li>`)
    .join("")}</ul>`;
}

function deepPanel(deep, sources) {
  let h = `<div class="panel">`;
  if (deep.rootCauses) {
    h += section("Why it happened",
      row("Trigger", deep.rootCauses.trigger) +
      row("Build-up", deep.rootCauses.buildup) +
      row("Deep force", deep.rootCauses.deepForce));
  }
  if (deep.butterflyChain && deep.butterflyChain.length) {
    h += section("Butterfly chain", `<ol class="chain">${deep.butterflyChain
      .map((b, i) => `<li><span class="n">${String(i + 1).padStart(2, "0")}</span>
        <span class="ev">${esc(b.event)}</span><span class="dt">${esc(b.detail)}</span></li>`)
      .join("")}</ol>`);
  }
  if (deep.connectDots) {
    const c = deep.connectDots;
    h += section("Connecting the dots",
      row("5 years ago", c.fiveYearsAgo) +
      row("From another field", c.differentField) +
      row("Hidden beneficiary", c.hiddenBeneficiary) +
      row("Official vs reality", c.officialVsReality) +
      row("If this were 1990", c.counterfactual1990) +
      row("6 months out", c.sixMonthsOut));
  }
  if (deep.narratives && deep.narratives.length) {
    h += section("Who's saying what",
      deep.narratives.map((n) => row(n.side, n.framing)).join(""));
  }
  if (deep.impacts && deep.impacts.length) {
    h += section("Impact map", deep.impacts.map((im) => {
      const col = SIGNAL_COLOR[(im.signal || "").toLowerCase()] || "#6b7a8d";
      return `<div class="impact">
        <span class="signal" style="color:${col};border:1px solid ${col}55">${esc(im.signal)}</span>
        <span class="kv"><b>${esc(im.domain)}:</b> ${esc(im.impact)}</span></div>`;
    }).join(""));
  }
  let split = "";
  if (deep.winners && deep.winners.length) split += section("Quiet winners", list(deep.winners, "▲", "#22c55e"));
  if (deep.losers && deep.losers.length) split += section("Quiet losers", list(deep.losers, "▼", "#ef4444"));
  if (split) h += `<div class="split">${split}</div>`;
  if (deep.historicalPattern) {
    h += section("Historical pattern",
      row("Parallel", deep.historicalPattern.parallel) +
      row("Lesson", deep.historicalPattern.lesson) +
      row("But different", deep.historicalPattern.divergence));
  }
  if (deep.blindSpots && deep.blindSpots.length) {
    h += section("What coverage misses", list(deep.blindSpots, "◇", "#38bdf8"));
  }
  if (deep.predictions && deep.predictions.length) {
    h += section("What happens next",
      deep.predictions.map((p) => row(p.horizon, p.prediction)).join(""));
  }
  if (deep.contrarianView) {
    h += section("Contrarian check", `<p class="callout">${esc(deep.contrarianView)}</p>`);
  }
  h += sourcesHtml(sources, "Investigated via");
  return h + `</div>`;
}

function agentsPanel(d) {
  let h = `<div class="panel">`;
  (d.agents || []).forEach((a) => {
    h += `<div class="agent">
      <div class="agent-head">
        <span class="emoji">${esc(a.emoji)}</span>
        <span class="role">${esc(a.role)}</span>
        <span class="lens">${esc(a.lens)}</span>
      </div>
      <p>${esc(a.take)}</p>
      <p class="micro"><b>History rhymes with:</b> ${esc(a.historicalConnection)}</p>
      <p class="micro"><b>Expects:</b> ${esc(a.prediction)}</p>
    </div>`;
  });
  if (d.synthesis) {
    h += `<div class="callout">
      <h4 style="font:500 10px 'JetBrains Mono',monospace;letter-spacing:.2em;text-transform:uppercase;color:#f5a623;margin-bottom:4px">Debate room</h4>
      ${row("They agree", d.synthesis.agreement)}
      ${row("They clash", d.synthesis.tension)}
      ${row("Contrarian", d.synthesis.contrarian)}</div>`;
  }
  h += sourcesHtml(d.agentSources, "Researched via");
  return h + `</div>`;
}

function sourcesHtml(sources, label) {
  if (!sources || !sources.length) return "";
  const links = sources.slice(0, 12)
    .map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>`)
    .join("");
  return `<div class="sources"><span class="lbl">${esc(label)}</span><div class="links">${links}</div></div>`;
}
function sourceList(sources, label) {
  const div = document.createElement("div");
  div.innerHTML = sourcesHtml(sources, label);
  return div.firstChild;
}

// ---------------------------------------------------------------- chat
function addMsg(cls, html) {
  const m = document.createElement("div");
  m.className = "msg " + cls;
  m.innerHTML = html;
  $("chatLog").appendChild(m);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
  return m;
}

async function sendChat(text) {
  addMsg("user", esc(text));
  const thinking = addMsg("bot thinking", "● investigating and forming my take…");
  $("chatInput").disabled = true;

  try {
    const data = await postJson("/api/chat", { message: text });
    thinking.remove();
    if (data.reply) {
      addMsg("bot", esc(data.reply));
      return;
    }
    const s = data.story, v = data.verdict;
    let h = `<span class="hl">${esc(s.headline)}</span>`;
    if (v.analysis) h += `<h5>My read</h5>${esc(v.analysis)}`;
    if (v.opinion) h += `<h5>My take</h5>${esc(v.opinion)}`;
    if (v.solution) h += `<h5>What should happen</h5>${esc(v.solution)}`;
    if (v.outcomes && v.outcomes.length) {
      h += `<h5>Likely outcomes</h5>` +
        v.outcomes.map((o) => `• ${esc(o.horizon)} — ${esc(o.outcome)}`).join("<br>");
    }
    addMsg("bot", h);
  } catch (e) {
    thinking.remove();
    addMsg("bot", `Sorry — ${esc(e.message)}`);
  } finally {
    $("chatInput").disabled = false;
    $("chatInput").focus();
  }
}

// ---------------------------------------------------------------- wire-up
$("todayBtn").onclick = loadToday;
$("searchBtn").onclick = () => searchTopic($("queryInput").value);
$("queryInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") searchTopic($("queryInput").value);
});
document.querySelectorAll(".cat").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".cat").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    searchTopic(`${btn.dataset.cat} news`);
  };
});

$("chatToggle").onclick = () => {
  $("chatPanel").classList.toggle("hidden");
  if (!$("chatPanel").classList.contains("hidden")) $("chatInput").focus();
};
$("chatClose").onclick = () => $("chatPanel").classList.add("hidden");
$("chatForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("chatInput").value.trim();
  if (!text) return;
  $("chatInput").value = "";
  sendChat(text);
});
