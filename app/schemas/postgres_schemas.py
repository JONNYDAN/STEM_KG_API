from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Any

class RootCategoryBase(BaseModel):
    id: str
    code: Optional[str] = None
    name: str
    description: Optional[str] = None

class RootCategoryCreate(RootCategoryBase):
    pass

class RootCategoryResponse(RootCategoryBase):
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CategoryBase(BaseModel):
    level: int = 1
    name: str
    root_category_id: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    code: Optional[str] = None
    diagram_count: int = 0
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DiagramBase(BaseModel):
    id: str
    category_id: int
    image_path: Optional[str] = None
    diagram_metadata: Optional[dict] = None  # Đổi tên từ metadata

class DiagramCreate(DiagramBase):
    pass

class DiagramResponse(DiagramBase):
    processed: bool = False
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class RootSubjectBase(BaseModel):
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: int = 0

class RootSubjectCreate(RootSubjectBase):
    id: Optional[int] = None  # Optional id for upsert operations

class RootSubjectResponse(RootSubjectBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

class SubjectBase(BaseModel):
    name: str
    root_subject_id: int
    synonyms: Optional[List[str]] = []
    description: Optional[str] = None
    categories: Optional[List[str]] = []  # Category names this subject belongs to

class SubjectCreate(SubjectBase):
    pass

class SubjectResponse(SubjectBase):
    id: int
    code: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class RelationshipBase(BaseModel):
    name: str
    description: Optional[str] = None
    inverse_relationship: Optional[str] = None
    semantic_type: Optional[str] = None

class RelationshipCreate(RelationshipBase):
    pass

class RelationshipResponse(RelationshipBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SROBase(BaseModel):
    subject_id: int
    relationship_id: int
    object_id: int
    diagram_id: Optional[str] = None
    confidence_score: Optional[float] = None
    context: Optional[str] = None

class SROCreate(SROBase):
    pass

class SROResponse(SROBase):
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
    
class RootCategoryUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

class CategoryUpdate(BaseModel):
    level: Optional[int] = None
    name: Optional[str] = None
    root_category_id: Optional[str] = None
    description: Optional[str] = None
    diagram_count: Optional[int] = None

class DiagramUpdate(BaseModel):
    category_id: Optional[int] = None
    image_path: Optional[str] = None
    processed: Optional[bool] = None
    diagram_metadata: Optional[dict] = None

class RootSubjectUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: Optional[int] = None

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    root_subject_id: Optional[int] = None
    synonyms: Optional[List[str]] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None

class RelationshipUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    inverse_relationship: Optional[str] = None
    semantic_type: Optional[str] = None

class SROUpdate(BaseModel):
    subject_id: Optional[int] = None
    relationship_id: Optional[int] = None
    object_id: Optional[int] = None
    diagram_id: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    context: Optional[str] = None

# Pagination and Filter schemas
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)

class SubjectFilter(BaseModel):
    name: Optional[str] = None
    root_subject_id: Optional[int] = None
    search_term: Optional[str] = None

class SROFilter(BaseModel):
    subject_name: Optional[str] = None
    relationship_name: Optional[str] = None
    object_name: Optional[str] = None
    diagram_id: Optional[str] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)