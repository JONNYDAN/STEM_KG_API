"""
Entity Schemas
Pydantic models for request/response validation
"""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from decimal import Decimal


# ==================== RootCategory ====================
class RootCategoryCreate(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class RootCategoryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Category ====================
class CategoryCreate(BaseModel):
    code: str
    name: str
    root_category_id: Optional[str] = None
    level: Optional[int] = 1
    description: Optional[str] = None
    diagram_count: Optional[int] = 0


class CategoryResponse(BaseModel):
    id: int
    code: Optional[str] = None
    name: str
    root_category_id: Optional[str] = None
    level: Optional[int] = None
    description: Optional[str] = None
    diagram_count: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== RootSubject ====================
class RootSubjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: Optional[int] = 0


class RootSubjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: Optional[int] = None

    class Config:
        from_attributes = True


# ==================== Subject ====================
class SubjectCreate(BaseModel):
    code: str
    name: str
    root_subject_id: Optional[int] = None
    synonyms: Optional[List[str]] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None


class SubjectResponse(BaseModel):
    id: int
    code: Optional[str] = None
    name: str
    root_subject_id: Optional[int] = None
    synonyms: Optional[Any] = None
    description: Optional[str] = None
    categories: Optional[Any] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Relationship ====================
class RelationshipCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    inverse_relationship: Optional[str] = None
    semantic_type: Optional[str] = None


class RelationshipResponse(BaseModel):
    id: int
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    inverse_relationship: Optional[str] = None
    semantic_type: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Diagram ====================
class DiagramCreate(BaseModel):
    id: str
    category_id: Optional[int] = None
    image_path: Optional[str] = None
    processed: Optional[bool] = False
    diagram_metadata: Optional[Any] = None


class DiagramResponse(BaseModel):
    id: str
    category_id: Optional[int] = None
    image_path: Optional[str] = None
    processed: Optional[bool] = None
    diagram_metadata: Optional[Any] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Triple (SubjectRelationshipObject) ====================
class TripleCreate(BaseModel):
    subject_id: int
    relationship_id: int
    object_id: int
    diagram_id: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    context: Optional[str] = None


class TripleResponse(BaseModel):
    id: int
    subject_id: int
    relationship_id: int
    object_id: int
    diagram_id: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    context: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
