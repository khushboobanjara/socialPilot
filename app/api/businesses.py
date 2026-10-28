from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.business import Business
from app.models.user import User
from app.schemas.business import BusinessCreate, BusinessResponse, BusinessUpdate

router = APIRouter(prefix="/api/businesses", tags=["Business profiles"])

def get_owned_business(business_id: int, owner_id: int, db: Session) -> Business:
    business = db.scalar(select(Business).where(Business.id == business_id, Business.owner_id == owner_id))
    if business is None:
        raise HTTPException(status_code=404, detail="Business profile not found")
    return business

@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
def create_business(payload: BusinessCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    business = Business(owner_id=user.id, **payload.model_dump())
    db.add(business)
    db.commit()
    db.refresh(business)
    return business

@router.get("", response_model=list[BusinessResponse])
def list_businesses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Business).where(Business.owner_id == user.id).order_by(Business.created_at.desc())).all())

@router.get("/{business_id}", response_model=BusinessResponse)
def read_business(business_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_owned_business(business_id, user.id, db)

@router.put("/{business_id}", response_model=BusinessResponse)
def update_business(business_id: int, payload: BusinessUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    business = get_owned_business(business_id, user.id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(business, key, value)
    db.commit()
    db.refresh(business)
    return business

@router.delete("/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business(business_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    business = get_owned_business(business_id, user.id, db)
    db.delete(business)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
