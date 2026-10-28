from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.business import Business
from app.models.content import ContentPost, PostVariant
from app.models.user import User
from app.schemas.content import GenerateRequest, ContentOut, ContentEdit
from app.services.ai_content_service import AIServiceError, generate_platform_content
router=APIRouter(prefix='/api/content',tags=['AI content'])
def owned_post(post_id,user_id,db):
    post=db.scalar(select(ContentPost).join(Business,ContentPost.business_id==Business.id).where(ContentPost.id==post_id,Business.owner_id==user_id).options(selectinload(ContentPost.variants)))
    if post is None: raise HTTPException(404,'Content draft not found')
    return post
@router.post('/generate',response_model=ContentOut,status_code=status.HTTP_201_CREATED)
def generate(payload:GenerateRequest,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    business=db.scalar(select(Business).where(Business.id==payload.business_id,Business.owner_id==user.id))
    if business is None: raise HTTPException(404,'Business profile not found')
    try: variants=generate_platform_content(business,payload.topic.strip(),payload.goal,payload.content_type,payload.platforms,payload.offer_details.strip(),payload.include_emojis)
    except AIServiceError as e: raise HTTPException(503,str(e)) from e
    post=ContentPost(business_id=business.id,created_by=user.id,topic=payload.topic.strip(),goal=payload.goal,content_type=payload.content_type,offer_details=payload.offer_details.strip(),status='draft')
    post.variants=[PostVariant(**v) for v in variants]; db.add(post); db.commit()
    return owned_post(post.id,user.id,db)
@router.get('',response_model=list[ContentOut])
def list_content(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    return list(db.scalars(select(ContentPost).join(Business,ContentPost.business_id==Business.id).where(Business.owner_id==user.id).options(selectinload(ContentPost.variants)).order_by(ContentPost.created_at.desc())).all())
@router.get('/{post_id}',response_model=ContentOut)
def get_content(post_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)): return owned_post(post_id,user.id,db)
@router.put('/{post_id}',response_model=ContentOut)
def update_content(post_id:int,payload:ContentEdit,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    post=owned_post(post_id,user.id,db)
    if payload.variants is not None:
        existing={v.platform:v for v in post.variants}; incoming=set()
        for v in payload.variants:
            incoming.add(v.platform)
            if v.platform in existing:
                existing[v.platform].caption=v.caption; existing[v.platform].hashtags=v.hashtags; existing[v.platform].call_to_action=v.call_to_action
            else: post.variants.append(PostVariant(**v.model_dump()))
        for platform,v in existing.items():
            if platform not in incoming: db.delete(v)
    db.commit(); return owned_post(post.id,user.id,db)


@router.post('/{post_id}/submit-approval', response_model=ContentOut)
def submit_for_approval(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = owned_post(post_id, user.id, db)
    if post.status not in ('draft', 'rejected'):
        raise HTTPException(409, f"Cannot submit a post with status '{post.status}'.")
    post.status = 'pending_approval'
    db.commit()
    return owned_post(post.id, user.id, db)

@router.post('/{post_id}/approve', response_model=ContentOut)
def approve_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = owned_post(post_id, user.id, db)
    if post.status != 'pending_approval':
        raise HTTPException(409, 'Only posts pending approval can be approved.')
    post.status = 'approved'
    db.commit()
    return owned_post(post.id, user.id, db)

@router.post('/{post_id}/reject', response_model=ContentOut)
def reject_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    post = owned_post(post_id, user.id, db)
    if post.status != 'pending_approval':
        raise HTTPException(409, 'Only posts pending approval can be rejected.')
    post.status = 'rejected'
    db.commit()
    return owned_post(post.id, user.id, db)
