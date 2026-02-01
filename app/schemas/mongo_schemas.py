# app/schemas/mongo_schemas.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class AnnotationText(BaseModel):
    value: str
    replacement_text: Optional[str] = None
    rectangle: List[List[int]]
    
    model_config = ConfigDict(from_attributes=True)

class AnnotationBlob(BaseModel):
    polygon: List[List[int]]
    point_count: int
    
    model_config = ConfigDict(from_attributes=True)

class DiagramAnnotationCreate(BaseModel):
    diagram_id: str
    category: str
    annotations: Dict[str, Any]
    
    model_config = ConfigDict(from_attributes=True)

class DiagramAnnotationResponse(DiagramAnnotationCreate):
    id: str = Field(alias="_id")
    processed_at: datetime
    metadata: Dict[str, Any]
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class SemanticRelationshipCreate(BaseModel):
    diagram_id: str
    category: str
    extracted_relationships: List[Dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)

class SemanticRelationshipResponse(SemanticRelationshipCreate):
    id: str = Field(alias="_id")
    processing_model: str
    created_at: datetime
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class RootSubjectDocCreate(BaseModel):
    root_subject_id: int
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: int = 0

    model_config = ConfigDict(from_attributes=True)

class RootSubjectDocResponse(RootSubjectDocCreate):
    id: str = Field(alias="_id")
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class SubjectDocCreate(BaseModel):
    subject_id: int
    name: str
    root_subject_id: int
    synonyms: Optional[List[str]] = []
    description: Optional[str] = None
    categories: Optional[List[str]] = []  # Category names this subject belongs to

    model_config = ConfigDict(from_attributes=True)

class SubjectDocResponse(SubjectDocCreate):
    id: str = Field(alias="_id")
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )