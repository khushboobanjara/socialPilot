from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.models.user import User
from app.services.ai_content_service import check_ollama
router=APIRouter(prefix='/api/ai',tags=['AI status'])
@router.get('/status')
def status(_:User=Depends(get_current_user)): return check_ollama()
