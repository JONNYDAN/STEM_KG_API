# app/schemas/neo4j_schemas.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class NodeSelector(BaseModel):
    label: str
    key: str = "id"
    value: Any

    model_config = ConfigDict(from_attributes=True)

class NodeCreate(BaseModel):
    # New flexible schema
    labels: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)

    # Legacy fields (STEM_NODE)
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class NodeResponse(NodeCreate):
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class RelationshipCreate(BaseModel):
    # New flexible schema
    from_node: Optional[NodeSelector] = None
    to_node: Optional[NodeSelector] = None
    relationship_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)

    # Legacy fields (STEM_NODE)
    from_node_id: Optional[str] = None
    to_node_id: Optional[str] = None
    name: Optional[str] = None
    confidence: Optional[float] = 0.0
    
    model_config = ConfigDict(from_attributes=True)

class RelationshipResponse(RelationshipCreate):
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class TripleQuery(BaseModel):
    subject: str
    relationship: str
    object: str
    
    model_config = ConfigDict(from_attributes=True)

class DiagramNode(BaseModel):
    diagram_id: str
    category: str
    nodes: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)

class NodeUpdateByKey(BaseModel):
    selector: NodeSelector
    properties: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)