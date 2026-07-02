from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import models
from database import engine
from routers import auth, projects, scans, ai_routes, reports, findings, system

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Navjeevan API", version="3.2")
app.mount("/static", StaticFiles(directory="."), name="static")

# Register all Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(scans.router)
app.include_router(ai_routes.router)
app.include_router(reports.router)
app.include_router(findings.router)
app.include_router(system.router)

@app.get("/dashboard", response_class=HTMLResponse)
def read_dashboard():
    with open("index.html", encoding="utf-8") as f:
        return f.read()