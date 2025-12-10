from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class TripleQuery(BaseModel):
    subject: str
    relationship: str
    object: str

class IntegrationResponse(BaseModel):
    query: Dict[str, str]
    timestamp: str
    postgres: List[Dict[str, Any]] = []
    neo4j: List[Dict[str, Any]] = []
    mongo: List[Dict[str, Any]] = []
    postgres_diagrams: Optional[List[Dict[str, Any]]] = None
    postgres_error: Optional[str] = None
    neo4j_error: Optional[str] = None
    mongo_error: Optional[str] = None
    inferred_category: Optional[str] = None
    inferred_diagrams: Optional[List[Dict[str, Any]]] = None