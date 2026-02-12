from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional, Dict

from app.database.postgres_conn import get_postgres_db
from app.services.postgres_service import PostgresService
from app.schemas import postgres_schemas as schemas

router = APIRouter(prefix="/postgres", tags=["PostgreSQL"])

# ========== ROOT CATEGORIES ==========
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
def get_root_category(
    category_id: str = Path(..., description="Root Category ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    category = service.get_root_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Root category not found")
    return category

@router.put("/root-categories/{category_id}", response_model=schemas.RootCategoryResponse)
def update_root_category(
    category_id: str = Path(..., description="Root Category ID"),
    category_update: schemas.RootCategoryUpdate = None,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    updated = service.update_root_category(category_id, category_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Root category not found")
    return updated

@router.delete("/root-categories/{category_id}")
def delete_root_category(
    category_id: str = Path(..., description="Root Category ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    if not service.delete_root_category(category_id):
        raise HTTPException(status_code=404, detail="Root category not found")
    return {"message": "Root category deleted successfully"}

# ========== CATEGORIES ==========
@router.post("/categories/", response_model=schemas.CategoryResponse)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    try:
        return service.create_category(category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/categories/", response_model=List[schemas.CategoryResponse])
def get_all_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_all_categories(skip=skip, limit=limit)

@router.get("/categories/{category_id}", response_model=schemas.CategoryResponse)
def get_category(
    category_id: int = Path(..., ge=1, description="Category ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    category = service.get_category(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.get("/categories/root/{root_category_id}", response_model=List[schemas.CategoryResponse])
def get_categories_by_root(
    root_category_id: str = Path(..., description="Root Category ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_categories_by_root(root_category_id)

@router.put("/categories/{category_id}", response_model=schemas.CategoryResponse)
def update_category(
    category_id: int = Path(..., ge=1, description="Category ID"),
    category_update: schemas.CategoryUpdate = None,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    try:
        updated = service.update_category(category_id, category_update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
    return updated

@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int = Path(..., ge=1, description="Category ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    if not service.delete_category(category_id):
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted successfully"}

# ========== DIAGRAMS ==========
@router.post("/diagrams/", response_model=schemas.DiagramResponse)
def create_diagram(
    diagram: schemas.DiagramCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.create_diagram(diagram)

@router.get("/diagrams/", response_model=List[schemas.DiagramResponse])
def get_all_diagrams(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_all_diagrams(skip=skip, limit=limit)

@router.get("/diagrams/{diagram_id}", response_model=schemas.DiagramResponse)
def get_diagram(
    diagram_id: str = Path(..., description="Diagram ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    diagram = service.get_diagram(diagram_id)
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")
    return diagram

@router.get("/diagrams/category/{category_id}", response_model=List[schemas.DiagramResponse])
def get_diagrams_by_category(
    category_id: int = Path(..., ge=1, description="Category ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_diagrams_by_category(category_id, skip=skip, limit=limit)

@router.put("/diagrams/{diagram_id}", response_model=schemas.DiagramResponse)
def update_diagram(
    diagram_id: str = Path(..., description="Diagram ID"),
    diagram_update: schemas.DiagramUpdate = None,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    updated = service.update_diagram(diagram_id, diagram_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Diagram not found")
    return updated

@router.delete("/diagrams/{diagram_id}")
def delete_diagram(
    diagram_id: str = Path(..., description="Diagram ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    if not service.delete_diagram(diagram_id):
        raise HTTPException(status_code=404, detail="Diagram not found")
    return {"message": "Diagram deleted successfully"}

# ========== ROOT SUBJECTS ==========
@router.post("/root-subjects/", response_model=schemas.RootSubjectResponse)
def create_root_subject(
    root_subject: schemas.RootSubjectCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.create_root_subject(root_subject)

@router.get("/root-subjects/", response_model=List[schemas.RootSubjectResponse])
def get_all_root_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_all_root_subjects(skip=skip, limit=limit)

@router.get("/root-subjects/{root_subject_id}", response_model=schemas.RootSubjectResponse)
def get_root_subject(
    root_subject_id: int = Path(..., ge=1, description="Root Subject ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    root_subject = service.get_root_subject(root_subject_id)
    if not root_subject:
        raise HTTPException(status_code=404, detail="Root subject not found")
    return root_subject

@router.get("/root-subjects/level/{level}", response_model=List[schemas.RootSubjectResponse])
def get_root_subjects_by_level(
    level: int = Path(..., ge=0, description="Level"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_root_subjects_by_level(level)

@router.put("/root-subjects/{root_subject_id}", response_model=schemas.RootSubjectResponse)
def update_root_subject(
    root_subject_id: int = Path(..., ge=1, description="Root Subject ID"),
    root_subject_update: schemas.RootSubjectUpdate = None,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    updated = service.update_root_subject(root_subject_id, root_subject_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Root subject not found")
    return updated

@router.delete("/root-subjects/{root_subject_id}")
def delete_root_subject(
    root_subject_id: int = Path(..., ge=1, description="Root Subject ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    if not service.delete_root_subject(root_subject_id):
        raise HTTPException(status_code=404, detail="Root subject not found")
    return {"message": "Root subject deleted successfully"}

# ========== SUBJECTS ==========
@router.post("/subjects/", response_model=schemas.SubjectResponse)
def create_subject(
    subject: schemas.SubjectCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    try:
        return service.create_subject(subject)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/subjects/", response_model=List[schemas.SubjectResponse])
def get_all_subjects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_all_subjects(skip=skip, limit=limit)

@router.get("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
def get_subject(
    subject_id: int = Path(..., ge=1, description="Subject ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    subject = service.get_subject(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject

@router.get("/subjects/root/{root_subject_id}", response_model=List[schemas.SubjectResponse])
def get_subjects_by_root(
    root_subject_id: int = Path(..., ge=1, description="Root Subject ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_subjects_by_root(root_subject_id, skip=skip, limit=limit)

@router.get("/subjects/search/", response_model=List[schemas.SubjectResponse])
def search_subjects(
    name: Optional[str] = Query(None, description="Search by name"),
    root_subject_id: Optional[int] = Query(None, ge=1, description="Filter by root subject"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.search_subjects(name=name, root_subject_id=root_subject_id)

@router.put("/subjects/{subject_id}", response_model=schemas.SubjectResponse)
def update_subject(
    subject_id: int = Path(..., ge=1, description="Subject ID"),
    subject_update: schemas.SubjectUpdate = None,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    try:
        updated = service.update_subject(subject_id, subject_update)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Subject not found")
    return updated

@router.delete("/subjects/{subject_id}")
def delete_subject(
    subject_id: int = Path(..., ge=1, description="Subject ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    if not service.delete_subject(subject_id):
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"message": "Subject deleted successfully"}

# ========== RELATIONSHIPS ==========
@router.post("/relationships/", response_model=schemas.RelationshipResponse)
def create_relationship(
    relationship: schemas.RelationshipCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.create_relationship(relationship)

@router.get("/relationships/", response_model=List[schemas.RelationshipResponse])
def get_all_relationships(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_all_relationships(skip=skip, limit=limit)

@router.get("/relationships/{relationship_id}", response_model=schemas.RelationshipResponse)
def get_relationship(
    relationship_id: int = Path(..., ge=1, description="Relationship ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    relationship = service.get_relationship(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return relationship

@router.get("/relationships/type/{semantic_type}", response_model=List[schemas.RelationshipResponse])
def get_relationships_by_type(
    semantic_type: str = Path(..., description="Semantic type (spatial, temporal, etc.)"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_relationships_by_type(semantic_type)

@router.get("/relationships/name/{name}", response_model=schemas.RelationshipResponse)
def get_relationship_by_name(
    name: str = Path(..., description="Relationship name"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    relationship = service.get_relationship_by_name(name)
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return relationship

@router.put("/relationships/{relationship_id}", response_model=schemas.RelationshipResponse)
def update_relationship(
    relationship_id: int = Path(..., ge=1, description="Relationship ID"),
    relationship_update: schemas.RelationshipUpdate = None,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    updated = service.update_relationship(relationship_id, relationship_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return updated

@router.delete("/relationships/{relationship_id}")
def delete_relationship(
    relationship_id: int = Path(..., ge=1, description="Relationship ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    if not service.delete_relationship(relationship_id):
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {"message": "Relationship deleted successfully"}

# ========== SUBJECT-RELATIONSHIP-OBJECT (SRO) ==========
@router.post("/sro/", response_model=schemas.SROResponse)
def create_sro(
    sro: schemas.SROCreate,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.create_sro(sro)

@router.get("/sro/", response_model=List[schemas.SROResponse])
def get_all_sros(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_all_sros(skip=skip, limit=limit)

@router.get("/sro/{sro_id}", response_model=schemas.SROResponse)
def get_sro(
    sro_id: int = Path(..., ge=1, description="SRO ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    sro = service.get_sro(sro_id)
    if not sro:
        raise HTTPException(status_code=404, detail="SRO not found")
    return sro

@router.get("/sro/diagram/{diagram_id}", response_model=List[schemas.SROResponse])
def get_sros_by_diagram(
    diagram_id: str = Path(..., description="Diagram ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_sros_by_diagram(diagram_id)

@router.get("/sro/subject/{subject_id}", response_model=List[schemas.SROResponse])
def get_sros_by_subject(
    subject_id: int = Path(..., ge=1, description="Subject ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_sros_by_subject(subject_id)

@router.get("/sro/object/{object_id}", response_model=List[schemas.SROResponse])
def get_sros_by_object(
    object_id: int = Path(..., ge=1, description="Object ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.get_sros_by_object(object_id)

@router.get("/sro/search/", response_model=List[Dict])
def search_sros(
    subject_name: Optional[str] = Query(None, description="Subject name"),
    relationship_name: Optional[str] = Query(None, description="Relationship name"),
    object_name: Optional[str] = Query(None, description="Object name"),
    diagram_id: Optional[str] = Query(None, description="Diagram ID"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.search_sros(
        subject_name=subject_name,
        relationship_name=relationship_name,
        object_name=object_name,
        diagram_id=diagram_id,
        min_confidence=min_confidence
    )

@router.put("/sro/{sro_id}", response_model=schemas.SROResponse)
def update_sro(
    sro_id: int = Path(..., ge=1, description="SRO ID"),
    sro_update: schemas.SROUpdate = None,
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    updated = service.update_sro(sro_id, sro_update)
    if not updated:
        raise HTTPException(status_code=404, detail="SRO not found")
    return updated

@router.delete("/sro/{sro_id}")
def delete_sro(
    sro_id: int = Path(..., ge=1, description="SRO ID"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    if not service.delete_sro(sro_id):
        raise HTTPException(status_code=404, detail="SRO not found")
    return {"message": "SRO deleted successfully"}

# ========== SEARCH AND UTILITY ==========
@router.get("/search/triple")
def search_categories_by_triple(
    subject: str = Query(..., description="Subject"),
    relationship: str = Query(..., description="Relationship"),
    object: str = Query(..., description="Object"),
    db: Session = Depends(get_postgres_db)
):
    service = PostgresService(db)
    return service.search_categories_by_triple(subject, relationship, object)

@router.get("/statistics")
def get_statistics(db: Session = Depends(get_postgres_db)):
    service = PostgresService(db)
    return service.get_statistics()