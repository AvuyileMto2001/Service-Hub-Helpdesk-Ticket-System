from flask import Flask, render_template, request, jsonify
import sqlite3, os, re
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'tcm_helpdesk.db')
app = Flask(__name__)

TECHNICIANS = [
    {'id': 1, 'name': 'Avuyile Mto', 'role': 'IT Intern', 'skills': 'Hardware, Helpdesk, Troubleshooting, Windows', 'languages': 'English, isiXhosa', 'certs': 'CCNA', 'photo': 'intern.jpg', 'online': True},
    {'id': 2, 'name': 'Daniel Smith', 'role': 'Senior IT Technician', 'skills': 'Networking, Cisco, VPN, Windows Server', 'languages': 'English, Afrikaans', 'certs': 'CCNA, CompTIA Network+', 'photo': 'staff-1.jpg', 'online': True},
    {'id': 3, 'name': 'Thando Ndlovu', 'role': 'Systems Engineer', 'skills': 'Microsoft 365, Azure, Active Directory, Security', 'languages': 'English, isiXhosa', 'certs': 'AZ-104, Security+', 'photo': 'staff-2.jpg', 'online': True},
    {'id': 4, 'name': 'Michael Jacobs', 'role': 'IT Support Specialist', 'skills': 'Applications, Printers, Hardware, Service Desk', 'languages': 'English, Afrikaans', 'certs': 'ITIL Foundation', 'photo': 'staff-3.jpg', 'online': False},
]

CATEGORIES = ['Hardware', 'Software', 'Network', 'Access & Identity', 'Security', 'Email & Collaboration', 'Other']


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS tickets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL, description TEXT NOT NULL, requester TEXT NOT NULL,
      email TEXT, source TEXT DEFAULT 'Portal', category TEXT, sentiment TEXT,
      urgency TEXT, priority TEXT, status TEXT DEFAULT 'New', assigned_to INTEGER,
      asset TEXT, created_at TEXT, updated_at TEXT, due_at TEXT, sla_minutes INTEGER,
      tags TEXT DEFAULT '', collision_user TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS ticket_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, event TEXT,
      actor TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS assets (
      id INTEGER PRIMARY KEY AUTOINCREMENT, asset_tag TEXT UNIQUE, device TEXT,
      serial TEXT, os TEXT, health TEXT, user TEXT, warranty TEXT, licenses TEXT
    );
    ''')
    if conn.execute('SELECT COUNT(*) FROM assets').fetchone()[0] == 0:
        conn.executemany('INSERT INTO assets(asset_tag,device,serial,os,health,user,warranty,licenses) VALUES(?,?,?,?,?,?,?,?)', [
            ('TCM-LT-1042','Lenovo ThinkPad T14','PF4ABC123','Windows 11 Pro','Healthy','Nomsa M.','2027-04-19','Microsoft 365, Defender'),
            ('TCM-DT-2088','Lenovo ThinkCentre M70q','PC9XYZ456','Windows 11 Pro','Warning','Sipho K.','2026-12-02','Microsoft 365'),
            ('TCM-LT-1177','Dell Latitude 5440','DL7QWE789','Windows 11 Pro','Healthy','Avuyile M.','2028-01-11','Microsoft 365, Visual Studio'),
        ])
    if conn.execute('SELECT COUNT(*) FROM tickets').fetchone()[0] == 0:
        now = datetime.now(timezone.utc)
        sample = [
            ('Laptop will not boot','My Lenovo laptop shows a BitLocker recovery screen after a BIOS update.','Nomsa M.','nomsa@tcm.co.za','Portal','Hardware','Neutral','High','High','In Progress',2,'TCM-LT-1042',now-timedelta(minutes=42),now-timedelta(minutes=5),now+timedelta(minutes=48),90,'bitlocker,bios'),
            ('Cannot connect to office Wi-Fi','Internet is down on my workstation and I need access urgently.','Sipho K.','sipho@tcm.co.za','Email','Network','Frustrated','Critical','Critical','New',2,'TCM-DT-2088',now-timedelta(minutes=12),now-timedelta(minutes=12),now+timedelta(minutes=18),30,'wifi,network'),
            ('Microsoft 365 password reset','Please reset my password so I can access Outlook and Teams.','Lerato P.','lerato@tcm.co.za','Chat','Access & Identity','Neutral','Medium','Medium','Pending',3,'',now-timedelta(hours=3),now-timedelta(hours=1),now+timedelta(hours=1),240,'password,m365'),
            ('Printer is not responding','The finance printer is offline again.','Mandla T.','mandla@tcm.co.za','Phone','Hardware','Neutral','Low','Low','New',4,'',now-timedelta(hours=1),now-timedelta(hours=1),now+timedelta(hours=7),480,'printer'),
            ('Suspicious email received','I received a suspicious attachment and think this could be phishing.','Zanele R.','zanele@tcm.co.za','Email','Security','Anxious','Critical','Critical','Escalated',3,'',now-timedelta(minutes=55),now-timedelta(minutes=10),now+timedelta(minutes=5),60,'phishing,security'),
        ]
        conn.executemany('''INSERT INTO tickets(title,description,requester,email,source,category,sentiment,urgency,priority,status,assigned_to,asset,created_at,updated_at,due_at,sla_minutes,tags) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', sample)
    conn.commit(); conn.close()


def analyze(text):
    t = text.lower()
    category = 'Other'
    rules = {
      'Security': ['phishing','virus','malware','suspicious','breach','security','ransomware'],
      'Network': ['wifi','wi-fi','internet','network','vpn','router','switch','connection','offline'],
      'Access & Identity': ['password','login','log in','account','bitlocker','access','locked out','mfa'],
      'Email & Collaboration': ['outlook','teams','email','mailbox','onedrive','sharepoint'],
      'Hardware': ['laptop','desktop','pc','printer','keyboard','mouse','screen','monitor','ssd','ram','bios'],
      'Software': ['windows','application','software','install','office','visual studio','program'],
    }
    for c, words in rules.items():
        if any(w in t for w in words): category = c; break
    negative = ['angry','frustrated','urgent','down','cannot','can\'t','failed','broken','not working','critical','emergency']
    positive = ['thanks','thank you','great','working now']
    sentiment = 'Frustrated' if sum(w in t for w in negative) >= 2 else ('Positive' if any(w in t for w in positive) else 'Neutral')
    critical = ['critical','emergency','breach','ransomware','phishing','production down','all users']
    high = ['urgent','cannot','can\'t','not working','offline','locked out','down']
    urgency = 'Critical' if any(w in t for w in critical) else ('High' if any(w in t for w in high) else 'Medium')
    if urgency == 'Critical': priority = 'Critical'; sla = 30
    elif urgency == 'High': priority = 'High'; sla = 90
    else: priority = 'Medium'; sla = 240
    if category == 'Other': priority = 'Low'; sla = 480
    return category, sentiment, urgency, priority, sla


def route(category):
    keywords = {
      'Network': ['Networking','Cisco','VPN'], 'Security': ['Security','Azure'],
      'Access & Identity': ['Microsoft 365','Azure','Active Directory'],
      'Email & Collaboration': ['Microsoft 365','Applications'], 'Hardware': ['Hardware','Helpdesk'],
      'Software': ['Applications','Windows']}
    wanted = keywords.get(category, ['Helpdesk'])
    candidates=[]
    for tech in TECHNICIANS:
        score = sum(1 for w in wanted if w.lower() in tech['skills'].lower()) + (1 if tech['online'] else 0)
        candidates.append((score, tech))
    return max(candidates, key=lambda x:x[0])[1]


def serialize(r):
    d = dict(r)
    tech = next((x for x in TECHNICIANS if x['id']==d.get('assigned_to')), None)
    d['assignee'] = tech['name'] if tech else 'Unassigned'
    d['assignee_role'] = tech['role'] if tech else ''
    return d

@app.route('/')
def index():
    return render_template('index.html', technicians=TECHNICIANS, categories=CATEGORIES)

@app.get('/api/dashboard')
def dashboard():
    conn=db(); rows=conn.execute('SELECT * FROM tickets ORDER BY id DESC').fetchall(); conn.close()
    tickets=[serialize(r) for r in rows]
    now=datetime.now(timezone.utc)
    for t in tickets:
        due=datetime.fromisoformat(t['due_at']) if t['due_at'] else now
        t['sla_remaining'] = max(0, int((due-now).total_seconds()/60))
        t['sla_breached'] = due < now
    stats={
      'open': sum(t['status'] not in ['Resolved','Closed'] for t in tickets),
      'critical': sum(t['priority']=='Critical' for t in tickets),
      'sla_risk': sum((not t['sla_breached']) and t['sla_remaining']<=30 and t['status'] not in ['Resolved','Closed'] for t in tickets),
      'resolved': sum(t['status'] in ['Resolved','Closed'] for t in tickets),
    }
    return jsonify({'tickets':tickets,'stats':stats,'technicians':TECHNICIANS})

@app.get('/api/assets')
def assets():
    conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM assets ORDER BY asset_tag')]; conn.close(); return jsonify(rows)

@app.post('/api/tickets')
def create_ticket():
    data=request.get_json() or {}
    title=data.get('title','Untitled request').strip(); desc=data.get('description','').strip(); requester=data.get('requester','Unknown').strip()
    category,sentiment,urgency,priority,sla=analyze(title+' '+desc)
    tech=route(category)
    now=datetime.now(timezone.utc); due=now+timedelta(minutes=sla)
    conn=db(); cur=conn.execute('''INSERT INTO tickets(title,description,requester,email,source,category,sentiment,urgency,priority,status,assigned_to,asset,created_at,updated_at,due_at,sla_minutes,tags) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (title,desc,requester,data.get('email',''),data.get('source','Portal'),category,sentiment,urgency,priority,'New',tech['id'],data.get('asset',''),now.isoformat(),now.isoformat(),due.isoformat(),sla,','.join(data.get('tags',[]))))
    tid=cur.lastrowid; conn.execute('INSERT INTO ticket_events(ticket_id,event,actor,created_at) VALUES(?,?,?,?)',(tid,f'AI classified as {category} / {priority}; routed to {tech["name"]}','Automation Engine',now.isoformat())); conn.commit(); conn.close()
    return jsonify({'id':tid,'category':category,'sentiment':sentiment,'urgency':urgency,'priority':priority,'sla_minutes':sla,'assigned_to':tech['name']})

@app.patch('/api/tickets/<int:ticket_id>')
def update_ticket(ticket_id):
    data=request.get_json() or {}; allowed={'status','assigned_to','priority','category','tags','collision_user'}
    fields=[]; vals=[]
    for k,v in data.items():
        if k in allowed: fields.append(f'{k}=?'); vals.append(v)
    fields.append('updated_at=?'); vals.append(datetime.now(timezone.utc).isoformat()); vals.append(ticket_id)
    conn=db(); conn.execute(f'UPDATE tickets SET {", ".join(fields)} WHERE id=?',vals)
    for k,v in data.items():
        if k in allowed: conn.execute('INSERT INTO ticket_events(ticket_id,event,actor,created_at) VALUES(?,?,?,?)',(ticket_id,f'{k} changed to {v}','Avuyile Mto',datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close(); return jsonify({'ok':True})

@app.post('/api/tickets/bulk')
def bulk():
    data=request.get_json() or {}; ids=data.get('ids',[]); action=data.get('action'); value=data.get('value')
    if not ids or not action: return jsonify({'error':'Select tickets and an action'}),400
    conn=db(); now=datetime.now(timezone.utc).isoformat()
    if action=='status': conn.executemany('UPDATE tickets SET status=?,updated_at=? WHERE id=?',[(value,now,i) for i in ids])
    elif action=='assign': conn.executemany('UPDATE tickets SET assigned_to=?,updated_at=? WHERE id=?',[(int(value),now,i) for i in ids])
    elif action=='priority': conn.executemany('UPDATE tickets SET priority=?,updated_at=? WHERE id=?',[(value,now,i) for i in ids])
    elif action=='tag': conn.executemany("UPDATE tickets SET tags=CASE WHEN tags='' THEN ? ELSE tags||','||? END,updated_at=? WHERE id=?",[(value,value,now,i) for i in ids])
    conn.commit(); conn.close(); return jsonify({'ok':True,'count':len(ids)})

@app.get('/api/tickets/<int:ticket_id>')
def ticket_detail(ticket_id):
    conn=db(); t=conn.execute('SELECT * FROM tickets WHERE id=?',(ticket_id,)).fetchone(); events=conn.execute('SELECT * FROM ticket_events WHERE ticket_id=? ORDER BY id DESC',(ticket_id,)).fetchall(); conn.close()
    if not t:return jsonify({'error':'Not found'}),404
    d=serialize(t); asset=None
    if d.get('asset'):
        conn=db(); a=conn.execute('SELECT * FROM assets WHERE asset_tag=?',(d['asset'],)).fetchone(); conn.close(); asset=dict(a) if a else None
    d['events']=[dict(e) for e in events]; d['asset_details']=asset; return jsonify(d)

@app.post('/api/tickets/<int:ticket_id>/collision')
def collision(ticket_id):
    user=(request.get_json() or {}).get('user','Avuyile Mto')
    conn=db(); conn.execute('UPDATE tickets SET collision_user=?,updated_at=? WHERE id=?',(user,datetime.now(timezone.utc).isoformat(),ticket_id)); conn.commit(); conn.close(); return jsonify({'ok':True})

@app.get('/api/search')
def search():
    q=request.args.get('q','').strip(); conn=db(); rows=conn.execute('SELECT * FROM tickets WHERE title LIKE ? OR description LIKE ? OR requester LIKE ? OR tags LIKE ? ORDER BY id DESC LIMIT 20',tuple([f'%{q}%']*4)).fetchall(); conn.close(); return jsonify([serialize(r) for r in rows])

if __name__=='__main__':
    init_db(); app.run(debug=True, host='127.0.0.1', port=5000)
