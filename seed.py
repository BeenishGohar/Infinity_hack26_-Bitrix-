"""Usage: python seed.py        -> create DB/tables and upsert the 10 demo users (safe to re-run)
          python seed.py reset  -> also delete generated projects/tasks (users are kept)"""
import os, sys, json
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
load_dotenv()

USERS = [
 ("ADMIN","Admin","admin@novaworks.example","ADMIN","Administrator",["Company overview","Transcript creation"]),
 ("PM01","Ayesha Khan","ayesha@novaworks.example","MANAGER","Web PM",["Web projects","Client coordination"]),
 ("PM02","Bilal Ahmed","bilal@novaworks.example","MANAGER","Mobile PM",["Mobile projects","Delivery planning"]),
 ("PM03","Hina Malik","hina@novaworks.example","MANAGER","AI PM",["AI projects","Requirement review"]),
 ("DEV01","Ali Raza","ali@novaworks.example","AGENT","Full-Stack",["React","Frontend integration"]),
 ("DEV02","Hamza Shah","hamza@novaworks.example","AGENT","Full-Stack",["Node.js","Databases","APIs"]),
 ("DEV03","Sara Noor","sara@novaworks.example","AGENT","App Developer",["Flutter","Mobile UI"]),
 ("DEV04","Usman Tariq","usman@novaworks.example","AGENT","App Developer",["Flutter","Integration","Testing"]),
 ("DEV05","Zain Abbas","zain@novaworks.example","AGENT","AI Developer",["LLMs","Extraction","Prompts"]),
 ("DEV06","Maryam Asif","maryam@novaworks.example","AGENT","AI Developer",["Retrieval","Document processing"]),
]
SCHEMA = [
"""CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(10) PRIMARY KEY, name VARCHAR(100) NOT NULL, email VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL, role ENUM('ADMIN','MANAGER','AGENT') NOT NULL,
  specialization VARCHAR(100), skills JSON)""",
"""CREATE TABLE IF NOT EXISTS projects (
  id CHAR(36) PRIMARY KEY, name VARCHAR(150) NOT NULL, client_name VARCHAR(150) NOT NULL,
  description TEXT, manager_id VARCHAR(10) NOT NULL, deadline DATE NOT NULL,
  FOREIGN KEY (manager_id) REFERENCES users(id))""",
"""CREATE TABLE IF NOT EXISTS tasks (
  id CHAR(36) PRIMARY KEY, project_id CHAR(36) NOT NULL, title VARCHAR(200) NOT NULL,
  description TEXT, assignee_id VARCHAR(10) NOT NULL, deadline DATE NOT NULL,
  estimated_hours DECIMAL(6,2) NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY (assignee_id) REFERENCES users(id))""",
]

def main():
    cfg = dict(host=os.getenv("DB_HOST","localhost"), port=int(os.getenv("DB_PORT",3306)),
               user=os.getenv("DB_USER","root"), password=os.getenv("DB_PASSWORD",""))
    name = os.getenv("DB_NAME","novaworks_crm")
    c = mysql.connector.connect(**cfg); cur = c.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4"); cur.execute(f"USE `{name}`")
    for s in SCHEMA: cur.execute(s)
    for uid, n, email, role, spec, skills in USERS:
        cur.execute("""INSERT INTO users (id,name,email,password_hash,role,specialization,skills)
            VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name),
            password_hash=VALUES(password_hash),role=VALUES(role),
            specialization=VALUES(specialization),skills=VALUES(skills)""",
            (uid, n, email, generate_password_hash("Demo123!"), role, spec, json.dumps(skills)))
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        cur.execute("DELETE FROM tasks"); cur.execute("DELETE FROM projects"); print("Projects and tasks cleared.")
    c.commit(); print(f"Database '{name}' ready with {len(USERS)} demo users.")

if __name__ == "__main__":
    main()
