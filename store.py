
import os, json
from pathlib import Path
from copy import deepcopy
from dotenv import load_dotenv
load_dotenv()

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
USERS = DATA / "users.json"
INCIDENTS = DATA / "incidents.json"

class Store:
    def __init__(self):
        self.mongo = None
        uri = os.getenv("MONGODB_URI","").strip()
        if uri:
            try:
                from pymongo import MongoClient
                c = MongoClient(uri, serverSelectionTimeoutMS=3000)
                c.admin.command("ping")
                db = c[os.getenv("MONGODB_DB","civic_pulse_india")]
                self.mongo = {"users":db["users"],"incidents":db["incidents"]}
                self.mongo["users"].create_index("email",unique=True)
                self.mongo["incidents"].create_index("incident_id",unique=True)
            except Exception:
                self.mongo = None

    def backend(self):
        return "MongoDB" if self.mongo else "Local JSON demo"

    def _read(self,p):
        return json.loads(p.read_text(encoding="utf-8") or "[]") if p.exists() else []

    def _write(self,p,d):
        p.write_text(json.dumps(d,indent=2,ensure_ascii=False,default=str),encoding="utf-8")

    def get_user(self,email):
        e = email.strip().lower()
        if self.mongo:
            return self.mongo["users"].find_one({"email":e},{"_id":0})
        return next((u for u in self._read(USERS) if u.get("email","").lower()==e),None)

    def create_user(self,u):
        u = deepcopy(u); u["email"] = u["email"].strip().lower()
        if self.get_user(u["email"]):
            raise ValueError("Account already exists")
        if self.mongo:
            self.mongo["users"].insert_one(u)
        else:
            arr=self._read(USERS); arr.append(u); self._write(USERS,arr)

    def update_user(self,email,updates):
        e=email.strip().lower()
        if self.mongo:
            self.mongo["users"].update_one({"email":e},{"$set":updates})
        else:
            arr=self._read(USERS)
            for u in arr:
                if u.get("email","").lower()==e:
                    u.update(updates)
            self._write(USERS,arr)

    def list_incidents(self):
        if self.mongo:
            docs=list(self.mongo["incidents"].find({},{"_id":0}))
            if not docs:
                seed=self._read(INCIDENTS)
                if seed:
                    self.mongo["incidents"].insert_many(seed)
                    docs=seed
            return docs
        return self._read(INCIDENTS)

    def get_incident(self,iid):
        if self.mongo:
            return self.mongo["incidents"].find_one({"incident_id":iid},{"_id":0})
        return next((x for x in self._read(INCIDENTS) if x.get("incident_id")==iid),None)

    def add_incident(self,x):
        if self.mongo:
            self.mongo["incidents"].insert_one(deepcopy(x))
        else:
            arr=self._read(INCIDENTS); arr.append(x); self._write(INCIDENTS,arr)

    def update_incident(self,iid,updates):
        if self.mongo:
            self.mongo["incidents"].update_one({"incident_id":iid},{"$set":updates})
        else:
            arr=self._read(INCIDENTS)
            for x in arr:
                if x.get("incident_id")==iid:
                    x.update(updates)
            self._write(INCIDENTS,arr)

    def user_incidents(self,email):
        e=email.lower()
        return [x for x in self.list_incidents() if e in [a.lower() for a in x.get("reporters",[])]]
