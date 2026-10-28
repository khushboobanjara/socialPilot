from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.db.database import Base,engine
from app import models  # register SQLAlchemy models
from app.api.auth import router as auth_router
from app.api.businesses import router as businesses_router
from app.api.content import router as content_router
from app.api.ai import router as ai_router
from app.api.schedules import router as schedules_router
from app.api.integrations import router as integrations_router
BASE_DIR=Path(__file__).resolve().parent.parent
Base.metadata.create_all(bind=engine)
app=FastAPI(title=settings.app_name,version='0.5.0',description='Week 5 social account connection foundation with MySQL.')
app.mount('/static',StaticFiles(directory=str(BASE_DIR/'static')),name='static')
app.include_router(auth_router); app.include_router(businesses_router); app.include_router(content_router); app.include_router(ai_router); app.include_router(schedules_router); app.include_router(integrations_router)
@app.get('/health',tags=['Health'])
def health(): return {'status':'ok','database':'mysql'}
@app.get('/',include_in_schema=False)
def home(): return FileResponse(BASE_DIR/'templates'/'index.html')
