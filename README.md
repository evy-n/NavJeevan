🛡️ NAVJEEVAN - Autonomous Web Security Intelligence Platform
Navjeevan ek AI-driven autonomous security platform hai jo human intervention ke bina reconnaissance se lekar report generation tak poora security audit kar sakta hai. Ye 120+ security tools ko orchestrate karta hai aur Groq AI (Llama 3) ka use karke attack paths generate karta hai.

🌟 Key Features
Autonomous Workflow State Machine: AI khud plan banata hai aur background mein tools chalata hai (Live tick ✅/❌).
120+ Tool Ecosystem: Subfinder, Nmap, Nuclei, FFUF, etc. ek hi searchable dropdown mein.
Live WebSocket Terminal: Tool ka output real-time line-by-line screen par aata hai.
AI Attack Path Engine: Saare bugs ko jod kar batata hai ki hacker system mein kaise ghus sakta hai.
Auto Tool Installer: Ek command se top 30+ tools automatically install ho jate hain.
Playwright Browser Intelligence: SPA (React/Angular) apps ko headless browser se scan karta hai.
DevOps CI/CD Webhook: GitHub Actions/Jenkins se auto-scan trigger karein.
🛠️ Tech Stack
Backend: Python, FastAPI, SQLAlchemy, WebSockets
Frontend: HTML, Tailwind CSS, Vis.js (Graph), Vanilla JS
AI Engine: Groq API (Llama 3 8B & 70B)
Database: SQLite (Easily upgradable to PostgreSQL)
📂 Folder Structure
NavJeevan/├── backend/│   ├── core/                   # Tool Registry & Async Agent Runtime│   ├── plugins/                # Tool Adapters (BasePlugin SDK)│   ├── ai_engine.py            # Groq AI Integration│   ├── database.py             # DB Connection│   ├── models.py               # DB Schema│   ├── setup_tools.py          # Auto-Installer Script│   ├── main.py                 # FastAPI Routes & WebSocket│   └── index.html              # Dashboard UI├── .env                        # API Keys & Config└── README.md
🚀 Installation & Setup
