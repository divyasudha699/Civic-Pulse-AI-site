
import os, uuid
from pathlib import Path
from datetime import datetime
import pandas as pd
import streamlit as st

from store import Store
from auth import valid_email, make_hash, check_hash, generate_otp, otp_expiry, otp_valid, send_otp_email
from logic import classify_text, department_for, find_duplicate, priority_score
from image_tools import photo_gps, reverse_geocode, analyze_photo

st.set_page_config(page_title="Civic Pulse AI India",page_icon="🏙️",layout="wide")
store=Store()
UPLOAD=Path(__file__).resolve().parent/"uploads"
UPLOAD.mkdir(exist_ok=True)

for k,v in {
    "role":None,"login_view":None,"citizen_email":None,"otp_stage":False,
    "otp_value":None,"otp_expiry":None,"otp_email":None,"theme":"Dark"
}.items():
    st.session_state.setdefault(k,v)

def apply_theme():
    if st.session_state.get("theme")=="Light":
        st.markdown("""<style>
        .stApp{background:#f5f7fb;color:#111827}
        [data-testid="stSidebar"]{background:#ffffff}
        .card{background:white;border:1px solid #e5e7eb;border-radius:16px;padding:18px;margin-bottom:12px}
        </style>""",unsafe_allow_html=True)
    else:
        st.markdown("""<style>
        .card{border:1px solid rgba(255,255,255,.12);border-radius:16px;padding:18px;margin-bottom:12px}
        </style>""",unsafe_allow_html=True)

apply_theme()

def logout():
    st.session_state.role=None
    st.session_state.login_view=None
    st.session_state.citizen_email=None
    st.session_state.otp_stage=False
    st.rerun()

def landing():
    st.title("🏙️ Civic Pulse AI")
    st.subheader("India Smart Civic Complaint Intelligence")
    st.write("Citizens report problems easily. Government teams receive one clear, prioritised incident instead of many repeated complaints.")
    c1,c2=st.columns(2)
    with c1:
        st.markdown("### 👤 Citizen Portal")
        st.write("Register → login with email/password/OTP → upload photo → report issue → track complaint.")
        if st.button("Open Citizen Portal",type="primary",use_container_width=True):
            st.session_state.login_view="citizen"; st.rerun()
    with c2:
        st.markdown("### 🏛️ Government / Admin Portal")
        st.write("Restricted dashboard for incidents, map, priority, duplicates, trends and departments.")
        if st.button("Open Government Portal",use_container_width=True):
            st.session_state.login_view="admin"; st.rerun()
    st.info("Academic prototype. It is not an official government grievance portal until an authority deploys/integrates it.")

def citizen_auth():
    st.title("👤 Citizen Portal")
    login,signup=st.tabs(["Login","Create Account"])
    with signup:
        with st.form("signup"):
            name=st.text_input("Full name")
            email=st.text_input("Email ID")
            phone=st.text_input("Mobile number")
            password=st.text_input("Create password",type="password")
            confirm=st.text_input("Confirm password",type="password")
            state=st.selectbox("State",["Karnataka","Andhra Pradesh","Tamil Nadu","Telangana","Kerala","Maharashtra","Other"])
            city=st.text_input("City / town")
            submit=st.form_submit_button("Create Account",type="primary")
        if submit:
            if not name.strip(): st.error("Enter your name.")
            elif not valid_email(email): st.error("Enter a valid email.")
            elif len(password)<6: st.error("Password must have at least 6 characters.")
            elif password!=confirm: st.error("Passwords do not match.")
            else:
                try:
                    salt,h=make_hash(password)
                    store.create_user({"name":name.strip(),"email":email.lower().strip(),"phone":phone.strip(),
                        "state":state,"city":city.strip(),"salt":salt,"hash":h,"theme":"Dark"})
                    st.success("Account created. Now open the Login tab.")
                except Exception as e: st.error(str(e))

    with login:
        if not st.session_state.otp_stage:
            with st.form("login"):
                email=st.text_input("Email ID")
                password=st.text_input("Password",type="password")
                go=st.form_submit_button("Continue to OTP",type="primary")
            if go:
                u=store.get_user(email)
                if not u or not check_hash(password,u["salt"],u["hash"]):
                    st.error("Incorrect email or password.")
                else:
                    code=generate_otp()
                    sent,msg=send_otp_email(email.lower().strip(),code)
                    st.session_state.otp_stage=True
                    st.session_state.otp_value=code
                    st.session_state.otp_expiry=otp_expiry()
                    st.session_state.otp_email=email.lower().strip()
                    if sent:
                        st.success(msg)
                    else:
                        st.warning("Email OTP is not configured yet. For local demo, use this OTP:")
                        st.code(code)
        else:
            st.write(f"OTP verification for **{st.session_state.otp_email}**")
            entered=st.text_input("Enter 6-digit OTP",max_chars=6)
            if st.button("Verify OTP",type="primary"):
                if otp_valid(st.session_state.otp_value,st.session_state.otp_expiry,entered):
                    st.session_state.role="citizen"
                    st.session_state.citizen_email=st.session_state.otp_email
                    u=store.get_user(st.session_state.citizen_email)
                    st.session_state.theme=u.get("theme","Dark")
                    st.session_state.otp_stage=False
                    st.rerun()
                else:
                    st.error("Wrong or expired OTP.")

    if st.button("← Back"):
        st.session_state.login_view=None; st.rerun()

def admin_auth():
    st.title("🏛️ Government / Admin Login")
    with st.form("admin_login"):
        email=st.text_input("Official email")
        password=st.text_input("Password",type="password")
        go=st.form_submit_button("Login",type="primary")
    if go:
        admin_email=os.getenv("ADMIN_EMAIL","admin@civicpulse.gov.in")
        admin_password=os.getenv("ADMIN_PASSWORD","Admin@123")
        if email.strip().lower()==admin_email.lower() and password==admin_password:
            st.session_state.role="admin"; st.rerun()
        else:
            st.error("Invalid admin login.")
    with st.expander("Local demo admin login"):
        st.code("admin@civicpulse.gov.in\nAdmin@123")
    if st.button("← Back"):
        st.session_state.login_view=None; st.rerun()

def citizen_portal():
    u=store.get_user(st.session_state.citizen_email)
    if not u:
        logout(); return

    st.sidebar.title("👤 Citizen")
    page=st.sidebar.radio("Menu",["Home","Report Problem","My Complaints","Track Complaint","Profile & Settings"])
    st.sidebar.caption(f"Signed in: {u.get('email')}")
    if st.sidebar.button("Logout"): logout()

    if page=="Home":
        st.title(f"Welcome, {u.get('name','Citizen')} 👋")
        mine=store.user_incidents(u["email"])
        c1,c2,c3=st.columns(3)
        c1.metric("My incidents",len(mine))
        c2.metric("Open / In Progress",sum(x.get("status")!="Resolved" for x in mine))
        c3.metric("Resolved",sum(x.get("status")=="Resolved" for x in mine))
        st.markdown("""
        <div class="card"><b>Fast complaint flow</b><br>
        📸 Add photo → 📍 detect/enter place → 🧠 identify problem → 🔁 merge duplicate → 🏛️ send one clear incident to government.
        </div>
        """,unsafe_allow_html=True)

    elif page=="Report Problem":
        st.title("📣 Report a Civic Problem")
        st.write("You do not need to know which department handles the problem.")

        photo=st.file_uploader("Upload a photo",type=["jpg","jpeg","png"])
        data=None; mime=None; lat=lon=None; geo={}
        if photo:
            data=photo.getvalue(); mime=photo.type or "image/jpeg"
            st.image(data,width=420)
            lat,lon=photo_gps(data)
            if lat is not None:
                geo=reverse_geocode(lat,lon)
                st.success(f"Photo GPS found: {lat:.6f}, {lon:.6f}")
            else:
                st.info("This photo has no GPS metadata. Enter the location below.")

            if st.button("🤖 Analyse Photo"):
                st.session_state["photo_ai"]=analyze_photo(data,mime)

            ai=st.session_state.get("photo_ai")
            if ai:
                if ai.get("available"):
                    st.success(f"AI result: {ai.get('category')} · severity {ai.get('severity')}")
                    st.write(ai.get("summary",""))
                else:
                    st.warning(ai.get("message","Photo AI is not configured."))

        with st.form("complaint_form"):
            desc=st.text_area("Describe the problem",placeholder="Example: Water is leaking continuously near the bus stop.")
            c1,c2=st.columns(2)
            state=c1.text_input("State",value=geo.get("state") or u.get("state",""))
            district=c2.text_input("District",value=geo.get("district",""))
            c3,c4=st.columns(2)
            city=c3.text_input("City / area",value=geo.get("city") or u.get("city",""))
            pin=c4.text_input("PIN code",value=geo.get("pincode",""))
            address=st.text_input("Street / landmark / address",value=geo.get("address",""))
            c5,c6=st.columns(2)
            lat_text=c5.text_input("Latitude (optional)",value=str(lat) if lat is not None else "")
            lon_text=c6.text_input("Longitude (optional)",value=str(lon) if lon is not None else "")
            genuine=st.checkbox("I confirm this complaint is genuine.")
            go=st.form_submit_button("Submit Complaint",type="primary")

        if go:
            if not desc.strip():
                st.error("Please describe the problem."); return
            if not genuine:
                st.error("Please confirm the declaration."); return

            text_cat,text_sev=classify_text(desc)
            ai=st.session_state.get("photo_ai",{})
            category=ai.get("category",text_cat) if ai.get("available") else text_cat
            severity=int(ai.get("severity",text_sev)) if ai.get("available") else text_sev
            try: lat_v=float(lat_text) if lat_text.strip() else None
            except: lat_v=None
            try: lon_v=float(lon_text) if lon_text.strip() else None
            except: lon_v=None

            dup,score=find_duplicate(store.list_incidents(),category,desc,lat_v,lon_v,pin,city)
            if dup:
                reporters=list(dup.get("reporters",[]))
                if u["email"] not in reporters:
                    reporters.append(u["email"])
                count=len(reporters)
                store.update_incident(dup["incident_id"],{
                    "reporters":reporters,
                    "reporter_count":count,
                    "priority_score":priority_score(max(severity,int(dup.get("severity",1))),count)
                })
                st.success("✅ Duplicate detected: same type + same place. Your report was merged into ONE existing incident.")
                st.info(f"Incident ID: **{dup['incident_id']}** · Total citizen reports: **{count}** · Match score: **{score}**")
            else:
                iid="IND-"+datetime.now().strftime("%Y%m%d")+"-"+uuid.uuid4().hex[:6].upper()
                saved=None
                if data:
                    ext=".png" if mime=="image/png" else ".jpg"
                    p=UPLOAD/f"{iid}{ext}"
                    p.write_bytes(data)
                    saved=str(p)
                inc={
                    "incident_id":iid,"category":category,"description":desc.strip(),
                    "state":state.strip(),"district":district.strip(),"city":city.strip(),
                    "address":address.strip(),"pincode":pin.strip(),
                    "latitude":lat_v,"longitude":lon_v,
                    "department":department_for(category),"status":"Open",
                    "severity":severity,"priority_score":priority_score(severity,1),
                    "created_at":datetime.now().isoformat(timespec="seconds"),
                    "reporter_count":1,"reporters":[u["email"]],
                    "photo_path":saved,"source":"Citizen portal"
                }
                store.add_incident(inc)
                st.success(f"✅ Complaint registered. Incident ID: **{iid}**")
                st.write(f"Category: **{category}** · Routed to: **{inc['department']}** · Priority: **{inc['priority_score']}/10**")

    elif page=="My Complaints":
        st.title("📋 My Complaints")
        mine=store.user_incidents(u["email"])
        if not mine:
            st.info("You have not reported any complaints yet.")
        else:
            for x in mine:
                st.markdown(f"""
                <div class="card">
                <b>{x.get('incident_id')}</b> — {x.get('category')}<br>
                {x.get('city')}, {x.get('state')}<br>
                Status: <b>{x.get('status')}</b> · Reports merged: <b>{x.get('reporter_count',1)}</b>
                </div>
                """,unsafe_allow_html=True)

    elif page=="Track Complaint":
        st.title("🔎 Track Complaint")
        iid=st.text_input("Enter Incident ID")
        if st.button("Track",type="primary"):
            inc=store.get_incident(iid.strip())
            if not inc:
                st.error("Incident not found.")
            elif u["email"] not in inc.get("reporters",[]):
                st.error("This incident is not linked to your account.")
            else:
                st.success(f"Status: {inc.get('status')}")
                st.write(f"**Department:** {inc.get('department')}")
                st.write(f"**Location:** {inc.get('address')}, {inc.get('city')}, {inc.get('state')} {inc.get('pincode')}")
                st.write(f"**Citizen reports merged:** {inc.get('reporter_count',1)}")

    else:
        st.title("👤 Profile & Settings")
        with st.form("profile"):
            name=st.text_input("Name",value=u.get("name",""))
            phone=st.text_input("Mobile",value=u.get("phone",""))
            state=st.text_input("State",value=u.get("state",""))
            city=st.text_input("City",value=u.get("city",""))
            theme=st.selectbox("Appearance",["Dark","Light"],index=0 if u.get("theme","Dark")=="Dark" else 1)
            go=st.form_submit_button("Save Settings",type="primary")
        st.text_input("Email",value=u.get("email",""),disabled=True)
        if go:
            store.update_user(u["email"],{"name":name,"phone":phone,"state":state,"city":city,"theme":theme})
            st.session_state.theme=theme
            st.success("Profile updated.")
            st.rerun()

def admin_portal():
    st.sidebar.title("🏛️ Government")
    page=st.sidebar.radio("Admin menu",[
        "Command Centre","Incident Queue","Map & Hotspots","Priority Board",
        "Duplicate Intelligence","Trends","Departments","System Setup"
    ])
    st.sidebar.caption("Citizen users cannot see these pages.")
    if st.sidebar.button("Logout"): logout()

    df=pd.DataFrame(store.list_incidents())
    if df.empty:
        st.warning("No incidents available.")
        return

    if page=="Command Centre":
        st.title("🏛️ Government Command Centre")
        c1,c2,c3,c4,c5=st.columns(5)
        c1.metric("Incidents",len(df))
        c2.metric("Open",int((df["status"]=="Open").sum()))
        c3.metric("In Progress",int((df["status"]=="In Progress").sum()))
        c4.metric("Resolved",int((df["status"]=="Resolved").sum()))
        c5.metric("Citizen reports",int(df["reporter_count"].fillna(1).sum()))
        st.subheader("High-priority incidents")
        st.dataframe(df.sort_values("priority_score",ascending=False)[
            ["incident_id","category","city","department","status","priority_score","reporter_count"]
        ].head(15),use_container_width=True,hide_index=True)
        st.subheader("Incidents by category")
        st.bar_chart(df["category"].value_counts())

    elif page=="Incident Queue":
        st.title("📥 Incident Queue")
        st.write("One row = one real incident. Repeated citizen complaints are merged into the same incident.")
        st.dataframe(df[["incident_id","category","description","city","pincode","department","status","priority_score","reporter_count"]],
                     use_container_width=True,hide_index=True,height=450)
        iid=st.selectbox("Select incident to update",df["incident_id"].tolist())
        inc=store.get_incident(iid)
        status=st.selectbox("Status",["Open","In Progress","Resolved"],
                            index=["Open","In Progress","Resolved"].index(inc.get("status","Open")))
        dept=st.text_input("Department",value=inc.get("department",""))
        if st.button("Save Update",type="primary"):
            store.update_incident(iid,{"status":status,"department":dept})
            st.success("Incident updated.")
            st.rerun()

    elif page=="Map & Hotspots":
        st.title("🗺️ India Complaint Map & Hotspots")
        m=df.dropna(subset=["latitude","longitude"]).copy()
        st.map(m.rename(columns={"latitude":"lat","longitude":"lon"})[["lat","lon"]])
        hot=df.groupby(["state","city","category"]).size().reset_index(name="incidents").sort_values("incidents",ascending=False)
        st.dataframe(hot,use_container_width=True,hide_index=True)

    elif page=="Priority Board":
        st.title("🚨 Priority Board")
        st.dataframe(df.sort_values(["priority_score","reporter_count"],ascending=False)[
            ["incident_id","category","city","severity","reporter_count","priority_score","status"]
        ],use_container_width=True,hide_index=True)

    elif page=="Duplicate Intelligence":
        st.title("🔁 Duplicate Intelligence")
        st.write("If two citizens report the same issue at the same place, Civic Pulse keeps ONE incident and increases its reporter count.")
        merged=df[df["reporter_count"].fillna(1)>1].copy()
        c1,c2=st.columns(2)
        c1.metric("Merged incident groups",len(merged))
        c2.metric("Extra duplicate reports merged",int((merged["reporter_count"]-1).sum()) if len(merged) else 0)
        if len(merged):
            st.dataframe(merged[["incident_id","category","city","description","reporter_count","priority_score","status"]],
                         use_container_width=True,hide_index=True)
        else:
            st.info("No duplicate groups yet.")

    elif page=="Trends":
        st.title("📈 Trends")
        d=df.copy()
        d["date"]=pd.to_datetime(d["created_at"],errors="coerce").dt.date
        st.line_chart(d.groupby("date").size())
        st.bar_chart(df["category"].value_counts())

    elif page=="Departments":
        st.title("🏢 Department Workload")
        st.dataframe(df.groupby(["department","status"]).size().reset_index(name="incidents"),
                     use_container_width=True,hide_index=True)

    else:
        st.title("⚙️ System Setup")
        st.write(f"Current storage: **{store.backend()}**")
        st.write("For final NoSQL demo, add your MongoDB Atlas connection in `.env`.")
        st.write("For real citizen OTP email, add SMTP settings in `.env`.")
        st.write("For real photo understanding, add a Gemini API key in `.env`.")
        st.info("India records included in this ZIP are demo data for testing the application, not official government complaint records.")

if st.session_state.role=="citizen":
    citizen_portal()
elif st.session_state.role=="admin":
    admin_portal()
elif st.session_state.login_view=="citizen":
    citizen_auth()
elif st.session_state.login_view=="admin":
    admin_auth()
else:
    landing()
