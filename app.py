import os, json, uuid, datetime as dt
from functools import wraps
from flask import Flask, request, session, jsonify
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from groq import Groq

load_dotenv()
app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

def conn():
    return mysql.connector.connect(host=os.getenv("DB_HOST","localhost"), port=int(os.getenv("DB_PORT",3306)),
        user=os.getenv("DB_USER","root"), password=os.getenv("DB_PASSWORD",""), database=os.getenv("DB_NAME","novaworks_crm"))

def query(sql, args=(), one=False):
    c = conn()
    try:
        cur = c.cursor(dictionary=True); cur.execute(sql, args)
        rows = cur.fetchall()
    finally:
        c.close()
    rows = [{k: (v.isoformat() if isinstance(v,(dt.date,dt.datetime)) else float(v) if hasattr(v,"as_tuple") else v)
             for k, v in r.items()} for r in rows]
    return (rows[0] if rows else None) if one else rows

def current_user():
    uid = session.get("uid")
    return query("SELECT id,name,email,role,specialization FROM users WHERE id=%s", (uid,), one=True) if uid else None

def login_required(roles=None):
    def deco(f):
        @wraps(f)
        def wrap(*a, **kw):
            u = current_user()
            if not u: return jsonify(error="Please log in."), 401
            if roles and u["role"] not in roles: return jsonify(error="You do not have access to this."), 403
            return f(u, *a, **kw)
        return wrap
    return deco

# ---------- access rules (enforced server-side) ----------
PROJ_SQL = """SELECT p.id,p.name,p.client_name,p.description,p.deadline,p.manager_id,m.name AS manager_name,
  (SELECT COUNT(*) FROM tasks t WHERE t.project_id=p.id {tf}) AS task_count,
  (SELECT COALESCE(SUM(estimated_hours),0) FROM tasks t WHERE t.project_id=p.id {tf}) AS total_hours
  FROM projects p JOIN users m ON m.id=p.manager_id {where} ORDER BY p.deadline"""
def get_projects(u):

    if u["role"] == "ADMIN": return query(PROJ_SQL.format(tf="", where=""))
    if u["role"] == "MANAGER":
        return query(PROJ_SQL.format(tf="", where="WHERE p.manager_id=%s"), (u["id"],))
    return query(PROJ_SQL.format(tf="AND t.assignee_id=%s",
                 where="WHERE p.id IN (SELECT project_id FROM tasks WHERE assignee_id=%s)"), (u["id"],) * 3)

def get_tasks(u, pid):
    base = "SELECT t.*,a.name AS assignee_name FROM tasks t JOIN users a ON a.id=t.assignee_id WHERE t.project_id=%s"
    if u["role"] == "AGENT": return query(base + " AND t.assignee_id=%s ORDER BY t.deadline", (pid, u["id"]))
    return query(base + " ORDER BY t.deadline", (pid,))

# ---------- auth ----------
@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    u = query("SELECT * FROM users WHERE email=%s", ((d.get("email") or "").strip().lower(),), one=True)
    if not u or not check_password_hash(u["password_hash"], d.get("password") or ""):
        return jsonify(error="Invalid email or password."), 401
    session.clear(); session["uid"] = u["id"]
    return jsonify(user={k: u[k] for k in ("id","name","email","role","specialization")})

@app.post("/api/logout")
def logout():
    session.clear(); return jsonify(ok=True)

@app.get("/api/me")
@login_required()
def me(u): return jsonify(user=u)

@app.get("/api/team")
@login_required()
def team(u): return jsonify(team=query("SELECT id,name,role,specialization,skills FROM users ORDER BY FIELD(role,'ADMIN','MANAGER','AGENT'),id"))

@app.get("/api/projects")
@login_required()
def projects(u): return jsonify(projects=get_projects(u))

@app.get("/api/projects/<pid>")
@login_required()
def project(u, pid):
    p = next((x for x in get_projects(u) if x["id"] == pid), None)
    if not p: return jsonify(error="Project not found."), 404
    return jsonify(project=p, tasks=get_tasks(u, pid))

# ---------- transcript automation ----------
SYSTEM = """You convert meeting transcripts into project-management records for NovaWorks Technologies.
Return ONLY a JSON object: {"projects":[{"name","clientName","description","managerId","deadline","tasks":[{"title","description","assigneeId","deadline","estimatedHours"}]}]}
Rules:
- Dates are YYYY-MM-DD (year 2026 unless stated). estimatedHours is a positive number of developer effort hours.
- managerId must be the id of a MANAGER and assigneeId the id of an AGENT from the supplied directory. Never invent people; people outside the directory (e.g. clients) are not employees.
- Follow the FINAL agreed decisions: when a date, hour estimate, owner or deadline is corrected later, use the corrected value and ignore earlier values.
- Ignore rejected or out-of-scope features (e.g. excluded payments, inventory, maps, email sending). Do not create tasks for them.
- Keep separate projects separate and separate tasks separate, even when one person owns several. Use the exact task names agreed in the meeting.
- Write a clear description for each project and task from the discussed scope.
- If a required value cannot be determined, use null for it (do not guess)."""

def validate(draft, users):
    errs, mgrs = [], {u["id"] for u in users if u["role"] == "MANAGER"}
    agents = {u["id"] for u in users if u["role"] == "AGENT"}
    def date(s):
        try: return dt.date.fromisoformat(s)
        except Exception: return None
    projs = draft.get("projects") if isinstance(draft, dict) else None
    if not isinstance(projs, list) or not projs: return ["The AI returned no projects."]
    for i, p in enumerate(projs, 1):
        L = f"Project {i} ({p.get('name') or 'unnamed'})"
        if not p.get("name"): errs.append(f"{L}: name is missing.")
        if not p.get("clientName"): errs.append(f"{L}: client is missing.")
        if p.get("managerId") not in mgrs: errs.append(f"{L}: manager is missing or not an existing manager.")
        pd = date(p.get("deadline"))
        if not pd: errs.append(f"{L}: deadline is missing or invalid.")
        if not p.get("tasks"): errs.append(f"{L}: has no tasks.")
        for j, t in enumerate(p.get("tasks") or [], 1):
            T = f"{L} / task {j} ({t.get('title') or 'untitled'})"
            if not t.get("title"): errs.append(f"{T}: title is missing.")
            if t.get("assigneeId") not in agents: errs.append(f"{T}: assignee is missing or not an existing agent.")
            h = t.get("estimatedHours")
            if not isinstance(h, (int, float)) or isinstance(h, bool) or h <= 0: errs.append(f"{T}: estimated hours must be positive.")
            td = date(t.get("deadline"))
            if not td: errs.append(f"{T}: deadline is missing or invalid.")
            elif pd and td > pd: errs.append(f"{T}: deadline is after the project deadline.")
    return errs

@app.post("/api/transcript")
@login_required(roles=["ADMIN"])
def from_transcript(u):
    text = ((request.get_json(silent=True) or {}).get("transcript") or "").strip()
    if not text: return jsonify(error="Paste a meeting transcript first."), 400
    users = query("SELECT id,name,role,skills FROM users")  # no passwords/emails sent to the AI
    directory = [{"id": x["id"], "name": x["name"], "role": x["role"], "skills": json.loads(x["skills"] or "[]")} for x in users]
    try:
        r = Groq(api_key=os.getenv("GROQ_API_KEY")).chat.completions.create(
                               model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), temperature=0,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": f"TEAM DIRECTORY:\n{json.dumps(directory)}\n\nTRANSCRIPT:\n{text}"}])
        draft = json.loads(r.choices[0].message.content)
    except Exception as e:
        app.logger.exception("AI failure")
        return jsonify(error="The AI could not process this transcript. Try again.", details=[str(e)[:200]]), 502
    errs = validate(draft, users)
    if errs: return jsonify(error="Some required details could not be resolved. Nothing was saved. Fix the transcript and try again.", details=errs), 422
    c = conn()
    try:
        c.start_transaction(); cur = c.cursor(); created = []; n = 0
        for p in draft["projects"]:
            pid = str(uuid.uuid4())
            cur.execute("INSERT INTO projects (id,name,client_name,description,manager_id,deadline) VALUES (%s,%s,%s,%s,%s,%s)",
                        (pid, p["name"], p["clientName"], p.get("description") or "", p["managerId"], p["deadline"]))
            for t in p["tasks"]:
                cur.execute("INSERT INTO tasks (id,project_id,title,description,assignee_id,deadline,estimated_hours) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (str(uuid.uuid4()), pid, t["title"], t.get("description") or "", t["assigneeId"], t["deadline"], t["estimatedHours"]))
                n += 1
            created.append({"id": pid, "name": p["name"], "tasks": len(p["tasks"])})
        c.commit()
    except Exception as e:
        c.rollback(); app.logger.exception("Save failed")
        return jsonify(error="Saving failed. Nothing was saved.", details=[str(e)[:200]]), 500
    finally:
        c.close()
    return jsonify(created=created, project_count=len(created), task_count=n)

@app.get("/")
def index(): return app.send_static_file("index.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
