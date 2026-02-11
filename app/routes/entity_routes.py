"""
Entity Management Routes
CRUD endpoints for all entities with tri-database synchronization
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database.postgres_conn import get_postgres_db
from app.services.entity_service import EntityService
from app.schemas.entity_schemas import (
    RootCategoryCreate, RootCategoryResponse,
    CategoryCreate, CategoryResponse,
    RootSubjectCreate, RootSubjectResponse,
    SubjectCreate, SubjectResponse,
    RelationshipCreate, RelationshipResponse,
    DiagramCreate, DiagramResponse,
    TripleCreate, TripleResponse,
)

router = APIRouter(prefix="/entities", tags=["Entity Management"])


def get_entity_service(db: Session = Depends(get_postgres_db)):
    return EntityService(db)


# ==================== RootCategory ====================
@router.post("/root-categories", response_model=RootCategoryResponse)
def create_root_category(payload: RootCategoryCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.create_root_category(payload.model_dump())
    return entity


@router.get("/root-categories", response_model=List[RootCategoryResponse])
def get_root_categories(service: EntityService = Depends(get_entity_service)):
    return service.get_root_categories()


@router.put("/root-categories/{entity_id}", response_model=RootCategoryResponse)
def update_root_category(entity_id: str, payload: RootCategoryCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.update_root_category(entity_id, payload.model_dump(exclude_unset=True))
    if not entity:
        raise HTTPException(status_code=404, detail="RootCategory not found")
    return entity


@router.delete("/root-categories/{entity_id}")
def delete_root_category(entity_id: str, service: EntityService = Depends(get_entity_service)):
    success = service.delete_root_category(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="RootCategory not found")
    return {"success": True, "message": "RootCategory deleted"}


# ==================== Category ====================
@router.post("/categories", response_model=CategoryResponse)
def create_category(payload: CategoryCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.create_category(payload.model_dump())
    return entity


@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(service: EntityService = Depends(get_entity_service)):
    try:
        result = service.get_categories()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching categories: {str(e)}")


@router.put("/categories/{entity_id}", response_model=CategoryResponse)
def update_category(entity_id: int, payload: CategoryCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.update_category(entity_id, payload.model_dump(exclude_unset=True))
    if not entity:
        raise HTTPException(status_code=404, detail="Category not found")
    return entity


@router.delete("/categories/{entity_id}")
def delete_category(entity_id: int, service: EntityService = Depends(get_entity_service)):
    success = service.delete_category(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"success": True, "message": "Category deleted"}


# ==================== RootSubject ====================
@router.post("/root-subjects", response_model=RootSubjectResponse)
def create_root_subject(payload: RootSubjectCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.create_root_subject(payload.model_dump())
    return entity


@router.get("/root-subjects", response_model=List[RootSubjectResponse])
def get_root_subjects(service: EntityService = Depends(get_entity_service)):
    return service.get_root_subjects()


@router.put("/root-subjects/{entity_id}", response_model=RootSubjectResponse)
def update_root_subject(entity_id: int, payload: RootSubjectCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.update_root_subject(entity_id, payload.model_dump(exclude_unset=True))
    if not entity:
        raise HTTPException(status_code=404, detail="RootSubject not found")
    return entity


@router.delete("/root-subjects/{entity_id}")
def delete_root_subject(entity_id: int, service: EntityService = Depends(get_entity_service)):
    success = service.delete_root_subject(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="RootSubject not found")
    return {"success": True, "message": "RootSubject deleted"}


# ==================== Subject ====================
@router.post("/subjects", response_model=SubjectResponse)
def create_subject(payload: SubjectCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.create_subject(payload.model_dump())
    return entity


@router.get("/subjects", response_model=List[SubjectResponse])
def get_subjects(service: EntityService = Depends(get_entity_service)):
    try:
        result = service.get_subjects()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching subjects: {str(e)}")


@router.put("/subjects/{entity_id}", response_model=SubjectResponse)
def update_subject(entity_id: int, payload: SubjectCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.update_subject(entity_id, payload.model_dump(exclude_unset=True))
    if not entity:
        raise HTTPException(status_code=404, detail="Subject not found")
    return entity


@router.delete("/subjects/{entity_id}")
def delete_subject(entity_id: int, service: EntityService = Depends(get_entity_service)):
    success = service.delete_subject(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Subject not found")
    return {"success": True, "message": "Subject deleted"}


# ==================== Relationship ====================
@router.post("/relationships", response_model=RelationshipResponse)
def create_relationship(payload: RelationshipCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.create_relationship(payload.model_dump())
    return entity


@router.get("/relationships", response_model=List[RelationshipResponse])
def get_relationships(service: EntityService = Depends(get_entity_service)):
    try:
        result = service.get_relationships()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching relationships: {str(e)}")


@router.put("/relationships/{entity_id}", response_model=RelationshipResponse)
def update_relationship(entity_id: int, payload: RelationshipCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.update_relationship(entity_id, payload.model_dump(exclude_unset=True))
    if not entity:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return entity


@router.delete("/relationships/{entity_id}")
def delete_relationship(entity_id: int, service: EntityService = Depends(get_entity_service)):
    success = service.delete_relationship(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {"success": True, "message": "Relationship deleted"}


# ==================== Diagram ====================
@router.post("/diagrams", response_model=DiagramResponse)
def create_diagram(payload: DiagramCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.create_diagram(payload.model_dump())
    return entity


@router.get("/diagrams", response_model=List[DiagramResponse])
def get_diagrams(service: EntityService = Depends(get_entity_service)):
    return service.get_diagrams()


@router.put("/diagrams/{entity_id}", response_model=DiagramResponse)
def update_diagram(entity_id: str, payload: DiagramCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.update_diagram(entity_id, payload.model_dump(exclude_unset=True))
    if not entity:
        raise HTTPException(status_code=404, detail="Diagram not found")
    return entity


@router.delete("/diagrams/{entity_id}")
def delete_diagram(entity_id: str, service: EntityService = Depends(get_entity_service)):
    success = service.delete_diagram(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Diagram not found")
    return {"success": True, "message": "Diagram deleted"}


# ==================== Triple (Subject-Relationship-Object) ====================
@router.post("/triples", response_model=TripleResponse)
def create_triple(payload: TripleCreate, service: EntityService = Depends(get_entity_service)):
    entity = service.create_triple(payload.model_dump())
    return entity


@router.get("/triples", response_model=List[TripleResponse])
def get_triples(service: EntityService = Depends(get_entity_service)):
    return service.get_triples()
