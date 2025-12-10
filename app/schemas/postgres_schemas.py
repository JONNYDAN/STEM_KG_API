from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List, Any

class RootCategoryBase(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

class RootCategoryCreate(RootCategoryBase):
    pass

class RootCategoryResponse(RootCategoryBase):
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CategoryBase(BaseModel):
    name: str
    root_category_id: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
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
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: int = 0

class RootSubjectCreate(RootSubjectBase):
    pass

class RootSubjectResponse(RootSubjectBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

class SubjectBase(BaseModel):
    name: str
    root_subject_id: int
    synonyms: Optional[List[str]] = []
    description: Optional[str] = None

class SubjectCreate(SubjectBase):
    pass

class SubjectResponse(SubjectBase):
    id: int
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