# NovaWorks Project Desk - AI Meeting to Project CRM

## Team
- Team name: [name] | Members: [4 names and responsibilities] | Repo: [GitHub URL]

## What Works
Login/logout (session based), admin transcript-to-projects via Groq AI, all-or-nothing save, project cards and detail,
read-only team directory, manager and agent views filtered **on the server**, persistent MySQL storage.

## Stack
Python Flask · vanilla HTML/CSS/JS · MySQL 8 (port 3306) · Groq (`llama-3.3-70b-versatile`) · Flask signed-cookie sessions, hashed passwords.

## Run Locally
```sh
git clone [YOUR_REPOSITORY_URL] && cd novaworks
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then fill in real values
python seed.py                                        # creates DB + tables + 10 demo users (safe to re-run)
python app.py                                         # open http://localhost:5000
```
MySQL must be running. Keep the `python app.py` terminal open.

## Environment Variables (`.env`, backend only)
`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `GROQ_API_KEY`, `GROQ_MODEL`, `SECRET_KEY`

## Demo Accounts (password `Demo123!` for all)
admin@novaworks.example · ayesha@ · bilal@ · hina@ (managers) · ali@ · hamza@ · sara@ · usman@ · zain@ · maryam@ (agents, all `@novaworks.example`)

## How Judges Can Test
1. Log in as admin → *Create from transcript* → *Load supplied transcript* (`static/sample/transcript.txt`) → Create. Expect 3 projects, 12 tasks.
2. Ayesha sees only UrbanCart; Ali sees his 3 tasks; Hamza sees 2 tasks across UrbanCart and QuickServe.
3. Direct URLs such as `/api/projects/<other-id>` return 404 for users without access.
4. Edit the transcript (e.g. QuickServe integration to 12 hours, 23 October) and create again.
5. Reset generated data between tests (keeps users): `python seed.py reset`

## Deployment
Local only. Demo video: [URL]

## Known Limitations
Free Groq rate limits may apply. Re-running creation adds duplicate projects (use `python seed.py reset`). Project/task editing not implemented.
