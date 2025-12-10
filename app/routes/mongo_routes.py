# app/routes/mongo_routes.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.services.mongo_service import MongoService
from app.schemas.mongo_schemas import (
    DiagramAnnotationCreate,
    SemanticRelationshipCreate
)

router = APIRouter(prefix="/mongo", tags=["MongoDB"])

@router.post("/annotations/", response_model=Dict[str, Any])
def create_annotation(annotation: DiagramAnnotationCreate):
    """Tạo annotation mới"""
    service = MongoService()
    try:
        result = service.create_diagram_annotation(annotation)
        return {"success": True, "annotation": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/annotations/{annotation_id}", response_model=Dict[str, Any])
def get_annotation(annotation_id: str):
    """Lấy annotation bằng ID"""
    service = MongoService()
    try:
        annotation = service.get_diagram_annotation_by_id(annotation_id)
        if not annotation:
            raise HTTPException(status_code=404, detail="Annotation not found")
        return annotation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/annotations/diagram/{diagram_id}", response_model=List[Dict[str, Any]])
def get_annotations_by_diagram(diagram_id: str):
    """Lấy annotations theo diagram"""
    service = MongoService()
    try:
        annotations = service.get_annotations_by_diagram(diagram_id)
        return annotations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/relationships/", response_model=Dict[str, Any])
def create_semantic_relationship(relationship: SemanticRelationshipCreate):
    """Tạo semantic relationship mới"""
    service = MongoService()
    try:
        result = service.create_semantic_relationship(relationship)
        return {"success": True, "relationship": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/relationships/{relationship_id}", response_model=Dict[str, Any])
def get_semantic_relationship(relationship_id: str):
    """Lấy semantic relationship bằng ID"""
    service = MongoService()
    try:
        relationship = service.get_semantic_relationship_by_id(relationship_id)
        if not relationship:
            raise HTTPException(status_code=404, detail="Relationship not found")
        return relationship
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/category/{category}", response_model=List[Dict[str, Any]])
def search_by_category(category: str):
    """Tìm annotations theo category"""
    service = MongoService()
    try:
        annotations = service.search_annotations_by_category(category)
        return annotations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))