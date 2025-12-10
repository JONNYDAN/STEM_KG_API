# app/schemas/neo4j_schemas.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime

class NodeCreate(BaseModel):
    id: str
    name: str
    type: str
    category: Optional[str] = None
    properties: Optional[Dict[str, Any]] = {}
    
    model_config = ConfigDict(from_attributes=True)

class NodeResponse(NodeCreate):
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class RelationshipCreate(BaseModel):
    from_node_id: str
    to_node_id: str
    relationship_type: str
    name: str
    confidence: Optional[float] = 0.0
    properties: Optional[Dict[str, Any]] = {}
    
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