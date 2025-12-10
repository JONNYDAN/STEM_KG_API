# app/services/mongo_service.py
from app.database.mongo_conn import get_mongo_db
from app.schemas.mongo_schemas import (
    DiagramAnnotationCreate, 
    SemanticRelationshipCreate
)
from typing import List, Dict, Any, Optional
from bson import ObjectId

class MongoService:
    def __init__(self):
        self.db = get_mongo_db()
        self.diagram_annotations = self.db["diagram_annotations"]
        self.semantic_relationships = self.db["semantic_relationships"]
    
    def create_diagram_annotation(self, annotation: DiagramAnnotationCreate) -> Dict[str, Any]:
        """Tạo annotation mới cho diagram"""
        data = annotation.model_dump()
        data["processed_at"] = datetime.now()
        data["metadata"] = data.get("metadata", {})
        
        result = self.diagram_annotations.insert_one(data)
        return self.get_diagram_annotation_by_id(str(result.inserted_id))
    
    def get_diagram_annotation_by_id(self, annotation_id: str) -> Optional[Dict[str, Any]]:
        """Lấy annotation bằng ID"""
        try:
            obj_id = ObjectId(annotation_id)
            result = self.diagram_annotations.find_one({"_id": obj_id})
            if result:
                result["_id"] = str(result["_id"])
            return result
        except:
            return None
    
    def get_annotations_by_diagram(self, diagram_id: str) -> List[Dict[str, Any]]:
        """Lấy tất cả annotations của một diagram"""
        results = self.diagram_annotations.find({"diagram_id": diagram_id})
        annotations = []
        for result in results:
            result["_id"] = str(result["_id"])
            annotations.append(result)
        return annotations
    
    def create_semantic_relationship(self, relationship: SemanticRelationshipCreate) -> Dict[str, Any]:
        """Tạo semantic relationship mới"""
        data = relationship.model_dump()
        data["created_at"] = datetime.now()
        data["processing_model"] = data.get("processing_model", "BERT+Visual")
        
        result = self.semantic_relationships.insert_one(data)
        return self.get_semantic_relationship_by_id(str(result.inserted_id))
    
    def get_semantic_relationship_by_id(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        """Lấy semantic relationship bằng ID"""
        try:
            obj_id = ObjectId(relationship_id)
            result = self.semantic_relationships.find_one({"_id": obj_id})
            if result:
                result["_id"] = str(result["_id"])
            return result
        except:
            return None
    
    def get_relationships_by_diagram(self, diagram_id: str) -> List[Dict[str, Any]]:
        """Lấy tất cả relationships của một diagram"""
        results = self.semantic_relationships.find({"diagram_id": diagram_id})
        relationships = []
        for result in results:
            result["_id"] = str(result["_id"])
            relationships.append(result)
        return relationships
    
    def search_annotations_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Tìm annotations theo category"""
        results = self.diagram_annotations.find({"category": category})
        annotations = []
        for result in results:
            result["_id"] = str(result["_id"])
            annotations.append(result)
        return annotations
    
    def update_annotation(self, annotation_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật annotation"""
        try:
            obj_id = ObjectId(annotation_id)
            self.diagram_annotations.update_one(
                {"_id": obj_id},
                {"$set": update_data}
            )
            return self.get_diagram_annotation_by_id(annotation_id)
        except:
            return None
    
    def delete_annotation(self, annotation_id: str) -> bool:
        """Xóa annotation"""
        try:
            obj_id = ObjectId(annotation_id)
            result = self.diagram_annotations.delete_one({"_id": obj_id})
            return result.deleted_count > 0
        except:
            return False

from datetime import datetime