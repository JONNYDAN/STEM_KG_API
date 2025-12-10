from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.postgres_conn import get_postgres_db
from app.services.postgres_service import PostgresService
from app.schemas import postgres_schemas as schemas

router = APIRouter(prefix="/postgres", tags=["PostgreSQL"])

@router.post("/root-categories/", response_model=schemas.RootCategoryResponse)
def create_root_category(
    category: schemas.RootCategoryCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.create_root_category(category)

@router.get("/root-categories/", response_model=List[schemas.RootCategoryResponse])
def get_all_root_categories(db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    return service.get_all_root_categories()

@router.get("/root-categories/{category_id}", response_model=schemas.RootCategoryResponse)
def get_root_category(category_id: str, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    category = service.get_root_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.put("/root-categories/{category_id}", response_model=schemas.RootCategoryResponse)
def update_root_category(
    category_id: str,
    category: schemas.RootCategoryCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    updated = service.update_root_category(category_id, category)
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
    return updated

@router.delete("/root-categories/{category_id}")
def delete_root_category(category_id: str, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    if not service.delete_root_category(category_id):
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted successfully"}

@router.post("/categories/", response_model=schemas.CategoryResponse)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    return service.create_category(category)

@router.get("/categories/{category_id}", response_model=schemas.CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    category = service.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.get("/categories/root/{root_category_id}", response_model=List[schemas.CategoryResponse])
def get_categories_by_root(root_category_id: str, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    return service.get_categories_by_root(root_category_id)

@router.post("/subjects/", response_model=schemas.SubjectResponse)
def create_subject(subject: schemas.SubjectCreate, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    return service.create_subject(subject)

@router.post("/relationships/", response_model=schemas.RelationshipResponse)
def create_relationship(relationship: schemas.RelationshipCreate, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    return service.create_relationship(relationship)

@router.post("/sro/", response_model=schemas.SROResponse)
def create_sro(sro: schemas.SROCreate, db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    return service.create_sro(sro)