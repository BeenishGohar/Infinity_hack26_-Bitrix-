const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let me = null;

async function api(path, opts = {}) {
  const r = await fetch("/api" + path, { headers: { "Content-Type": "application/json" }, credentials: "same-origin", ...opts });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && path !== "/login") { showLogin(); throw new Error("Please log in."); }
  if (!r.ok) { const e = new Error(data.error || "Something went wrong."); e.details = data.details; throw e; }
  return data;
}

function showLogin() { me = null; $("#app").classList.add("hidden"); $("#login").classList.remove("hidden"); }

function start(user) {
  me = user;
  $("#login").classList.add("hidden"); $("#app").classList.remove("hidden");
  $("#who").textContent = `${user.name} (${user.role.toLowerCase()})`;
  const tabs = [["projects", me.role === "AGENT" ? "My tasks" : me.role === "MANAGER" ? "My projects" : "Projects"], ["team", "Team"]];
  if (me.role === "ADMIN") tabs.push(["create", "Create from transcript"]);
  $("#nav").innerHTML = tabs.map(([k, l]) => `<a data-t="${k}" tabindex="0" role="button">${l}</a>`).join("");
  go("projects");
}

function go(tab) {
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.t === tab));
  ({ projects: viewProjects, team: viewTeam, create: viewCreate })[tab]();
}

async function viewProjects() {
  $("#view").innerHTML = '<p class="muted">Loading…</p>';
  const { projects } = await api("/projects");
  if (!projects.length) {
    $("#view").innerHTML = `<div class="empty">${me.role === "ADMIN" ? "No projects yet. Use Create from transcript to add some." : "Nothing is assigned to you yet."}</div>`;
    return;
  }
  const title = me.role === "AGENT" ? "Projects with my tasks" : "Projects";
  $("#view").innerHTML = `<h2>${title}</h2><div class="grid">` + projects.map(p => `
    <article class="card" data-id="${p.id}" tabindex="0" role="button">
      <h3>${esc(p.name)}</h3><div class="muted">${esc(p.client_name)}</div>
      <div class="meta"><span>Manager: ${esc(p.manager_name)}</span><span>Due ${p.deadline}</span></div>
      <div class="meta"><span>${p.task_count} task${p.task_count == 1 ? "" : "s"}</span><span>${p.total_hours} h</span></div>
    </article>`).join("") + "</div>";
}

async function viewProject(id) {
  const { project: p, tasks } = await api("/projects/" + id);
  const mine = me.role === "AGENT" ? "Your tasks in this project" : "Tasks";
  $("#view").innerHTML = `<button class="back">← Back to projects</button>
    <h2>${esc(p.name)}</h2>
    <p class="muted">Client: ${esc(p.client_name)} · Manager: ${esc(p.manager_name)} · Deadline: ${p.deadline}</p>
    <p>${esc(p.description)}</p><h3>${mine}</h3>
    <div class="table-wrap"><table><thead><tr><th>Task</th><th>Description</th><th>Assigned to</th><th>Deadline</th><th>Hours</th></tr></thead><tbody>` +
    tasks.map(t => `<tr><td><strong>${esc(t.title)}</strong></td><td>${esc(t.description)}</td><td>${esc(t.assignee_name)}</td><td>${t.deadline}</td><td>${t.estimated_hours}</td></tr>`).join("") +
    "</tbody></table></div>";
  $("#view .back").onclick = () => go("projects");
}

async function viewTeam() {
  const { team } = await api("/team");
  $("#view").innerHTML = `<h2>Team directory</h2><div class="table-wrap"><table><thead><tr><th>Name</th><th>Role</th><th>Specialization</th></tr></thead><tbody>` +
    team.map(u => `<tr><td>${esc(u.name)}</td><td>${esc(u.role.toLowerCase())}</td><td>${esc(u.specialization)}</td></tr>`).join("") + "</tbody></table></div>";
}

function viewCreate() {
  $("#view").innerHTML = `<h2>Create from transcript</h2>
    <p class="muted">Paste the meeting transcript. Projects and tasks are created only if every required detail is resolved.</p>
    <textarea id="tx" placeholder="Paste the meeting transcript here"></textarea>
    <div class="row"><button id="go" class="btn">Create from transcript</button><button id="sample" class="btn ghost" type="button">Load supplied transcript</button></div>
    <div id="out"></div>`;
  $("#sample").onclick = async () => { $("#tx").value = await (await fetch("/sample/transcript.txt")).text(); };
  $("#go").onclick = async () => {
    const btn = $("#go"), out = $("#out");
    btn.disabled = true; btn.textContent = "Reading the meeting…"; out.innerHTML = "";
    try {
      const r = await api("/transcript", { method: "POST", body: JSON.stringify({ transcript: $("#tx").value }) });
      out.innerHTML = `<div class="box ok"><strong>Created ${r.project_count} projects with ${r.task_count} tasks.</strong><ul>` +
        r.created.map(c => `<li>${esc(c.name)}: ${c.tasks} tasks</li>`).join("") + `</ul><div class="row"><button class="btn" id="seeP">View projects</button></div></div>`;
      $("#seeP").onclick = () => go("projects");
    } catch (e) {
      out.innerHTML = `<div class="box bad"><strong>${esc(e.message)}</strong>` +
        (e.details ? "<ul>" + e.details.map(d => `<li>${esc(d)}</li>`).join("") + "</ul>" : "") + "</div>";
    } finally { btn.disabled = false; btn.textContent = "Create from transcript"; }
  };
}

document.addEventListener("click", e => {
  const nav = e.target.closest("#nav a"); if (nav) return go(nav.dataset.t);
  const card = e.target.closest(".card"); if (card) viewProject(card.dataset.id);
});
document.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.matches(".card,#nav a")) e.target.click(); });

$("#loginForm").onsubmit = async e => {
  e.preventDefault(); $("#loginErr").textContent = "";
  try { start((await api("/login", { method: "POST", body: JSON.stringify({ email: $("#email").value, password: $("#password").value }) })).user); }
  catch (err) { $("#loginErr").textContent = err.message; }
};
$("#logout").onclick = async () => { await api("/logout", { method: "POST" }).catch(() => {}); showLogin(); };

api("/me").then(r => start(r.user)).catch(showLogin);
