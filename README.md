# TCM ServiceHub — IT Helpdesk Prototype

A professional blue-and-white IT service management/helpdesk prototype for TCM, built with **HTML, CSS, JavaScript, Python (Flask), and SQLite**.

## Included features
- AI-style ticket categorization: category, sentiment, urgency and priority
- Skills-based automatic routing to technicians
- Multi-tier SLA timers and SLA-risk indicators
- Omnichannel source field: Portal, Email, Chat, Phone
- Asset/CMDB sidebar mapping with hardware, OS, health, warranty and licenses
- Collision detection indicator when a technician opens a ticket
- Ctrl/Cmd + K global command palette
- Smart macro-ready architecture and bulk ticket processing
- Queue filtering/searching and status updates
- Persistent ticket database and ticket event/audit timeline
- TCM logo and supplied staff photos integrated into the UI
- Technician directory with skills, languages and certifications

## Run locally
1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run: `pip install -r requirements.txt`
4. Run: `python app.py`
5. Open: `http://127.0.0.1:5000`

The SQLite database `tcm_helpdesk.db` is created automatically and stores tickets, assets and ticket events.

> The NLP/AI categorization in this prototype is a local rule-based simulation. For production use, replace `analyze()` with a secured NLP/LLM service and add authentication, RBAC, encryption, backups, audit controls and integrations with TCM's real email/chat/telephony/CMDB systems.
