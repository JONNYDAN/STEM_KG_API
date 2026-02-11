"""
Entity Management Service
Handles CRUD operations for all entities with tri-database synchronization
MongoDB, PostgreSQL, and Neo4j are kept in sync
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.database.mongo_conn import get_mongo_db
from app.database.neo4j_conn import get_neo4j_session
from app.models.postgres_models import (
    RootCategory, Category, RootSubject, Subject, 
    Relationship, Diagram, SubjectRelationshipObject
)


class EntityService:
    def __init__(self, pg_db: Session):
        self.pg_db = pg_db
        self.mongo_db = get_mongo_db()
        
    def _sync_to_mongo(self, collection_name: str, entity_id: str, data: Dict[str, Any]):
        """Sync entity data to MongoDB"""
        collection = self.mongo_db[collection_name]
        data["_sync_id"] = entity_id
        data["updated_at"] = datetime.utcnow()
        collection.update_one(
            {"_sync_id": entity_id},
            {"$set": data},
            upsert=True
        )
    
    def _delete_from_mongo(self, collection_name: str, entity_id: str):
        """Delete entity from MongoDB"""
        collection = self.mongo_db[collection_name]
        collection.delete_one({"_sync_id": entity_id})
    
    def _sync_to_neo4j(self, label: str, entity_id: str, properties: Dict[str, Any]):
        """Sync entity data to Neo4j"""
        session = get_neo4j_session()
        try:
            # Prepare properties for Neo4j (remove None values)
            props = {k: v for k, v in properties.items() if v is not None}
            props["entity_id"] = entity_id
            
            # Create or update node
            query = f"""
            MERGE (n:{label} {{entity_id: $entity_id}})
            SET n += $props
            RETURN n
            """
            session.run(query, entity_id=entity_id, props=props)
        finally:
            session.close()
    
    def _delete_from_neo4j(self, label: str, entity_id: str):
        """Delete entity from Neo4j"""
        session = get_neo4j_session()
        try:
            query = f"MATCH (n:{label} {{entity_id: $entity_id}}) DETACH DELETE n"
            session.run(query, entity_id=entity_id)
        finally:
            session.close()
    
    def _create_relationship_in_neo4j(self, subject_id: str, rel_name: str, object_id: str, properties: Dict = None):
        """Create relationship in Neo4j"""
        session = get_neo4j_session()
        try:
            props = properties or {}
            query = f"""
            MATCH (s:Subject {{entity_id: $subject_id}})
            MATCH (o:Subject {{entity_id: $object_id}})
            MERGE (s)-[r:{rel_name}]->(o)
            SET r += $props
            RETURN r
            """
            session.run(query, subject_id=subject_id, object_id=object_id, props=props)
        finally:
            session.close()
    
    # ==================== RootCategory ====================
    def create_root_category(self, data: Dict[str, Any]) -> RootCategory:
        # PostgreSQL
        entity = RootCategory(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        # MongoDB
        self._sync_to_mongo("root_categories", entity.id, {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "created_at": entity.created_at,
        })
        
        # Neo4j
        self._sync_to_neo4j("RootCategory", entity.id, {
            "name": entity.name,
            "description": entity.description,
        })
        
        return entity
    
    def update_root_category(self, entity_id: str, data: Dict[str, Any]) -> Optional[RootCategory]:
        entity = self.pg_db.query(RootCategory).filter(RootCategory.id == entity_id).first()
        if not entity:
            return None
        
        # Update PostgreSQL
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        # Sync to MongoDB and Neo4j
        self._sync_to_mongo("root_categories", entity.id, {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
        })
        self._sync_to_neo4j("RootCategory", entity.id, {
            "name": entity.name,
            "description": entity.description,
        })
        
        return entity
    
    def delete_root_category(self, entity_id: str) -> bool:
        entity = self.pg_db.query(RootCategory).filter(RootCategory.id == entity_id).first()
        if not entity:
            return False
        
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("root_categories", entity_id)
        self._delete_from_neo4j("RootCategory", entity_id)
        
        return True
    
    def get_root_categories(self) -> List[RootCategory]:
        return self.pg_db.query(RootCategory).all()
    
    # ==================== Category ====================
    def create_category(self, data: Dict[str, Any]) -> Category:
        entity = Category(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("categories", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "root_category_id": entity.root_category_id,
            "level": entity.level,
            "description": entity.description,
            "diagram_count": entity.diagram_count,
        })
        
        self._sync_to_neo4j("Category", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "level": entity.level,
            "description": entity.description,
        })
        
        return entity
    
    def update_category(self, entity_id: int, data: Dict[str, Any]) -> Optional[Category]:
        entity = self.pg_db.query(Category).filter(Category.id == entity_id).first()
        if not entity:
            return None
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("categories", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "root_category_id": entity.root_category_id,
            "level": entity.level,
            "description": entity.description,
            "diagram_count": entity.diagram_count,
        })
        
        self._sync_to_neo4j("Category", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "level": entity.level,
            "description": entity.description,
        })
        
        return entity
    
    def delete_category(self, entity_id: int) -> bool:
        entity = self.pg_db.query(Category).filter(Category.id == entity_id).first()
        if not entity:
            return False
        
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("categories", str(entity_id))
        self._delete_from_neo4j("Category", str(entity_id))
        
        return True
    
    def get_categories(self) -> List[Category]:
        return self.pg_db.query(Category).all()
    
    # ==================== RootSubject ====================
    def create_root_subject(self, data: Dict[str, Any]) -> RootSubject:
        entity = RootSubject(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("root_subjects", str(entity.id), {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "parent_id": entity.parent_id,
            "level": entity.level,
        })
        
        self._sync_to_neo4j("RootSubject", str(entity.id), {
            "name": entity.name,
            "description": entity.description,
            "level": entity.level,
        })
        
        return entity
    
    def update_root_subject(self, entity_id: int, data: Dict[str, Any]) -> Optional[RootSubject]:
        entity = self.pg_db.query(RootSubject).filter(RootSubject.id == entity_id).first()
        if not entity:
            return None
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("root_subjects", str(entity.id), {
            "id": entity.id,
            "name": entity.name,
            "description": entity.description,
            "parent_id": entity.parent_id,
            "level": entity.level,
        })
        
        self._sync_to_neo4j("RootSubject", str(entity.id), {
            "name": entity.name,
            "description": entity.description,
            "level": entity.level,
        })
        
        return entity
    
    def delete_root_subject(self, entity_id: int) -> bool:
        entity = self.pg_db.query(RootSubject).filter(RootSubject.id == entity_id).first()
        if not entity:
            return False
        
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("root_subjects", str(entity_id))
        self._delete_from_neo4j("RootSubject", str(entity_id))
        
        return True
    
    def get_root_subjects(self) -> List[RootSubject]:
        return self.pg_db.query(RootSubject).all()
    
    # ==================== Subject ====================
    def create_subject(self, data: Dict[str, Any]) -> Subject:
        entity = Subject(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("subjects", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "root_subject_id": entity.root_subject_id,
            "synonyms": entity.synonyms,
            "description": entity.description,
            "categories": entity.categories,
        })
        
        self._sync_to_neo4j("Subject", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
        })
        
        return entity
    
    def update_subject(self, entity_id: int, data: Dict[str, Any]) -> Optional[Subject]:
        entity = self.pg_db.query(Subject).filter(Subject.id == entity_id).first()
        if not entity:
            return None
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("subjects", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "root_subject_id": entity.root_subject_id,
            "synonyms": entity.synonyms,
            "description": entity.description,
            "categories": entity.categories,
        })
        
        self._sync_to_neo4j("Subject", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
        })
        
        return entity
    
    def delete_subject(self, entity_id: int) -> bool:
        entity = self.pg_db.query(Subject).filter(Subject.id == entity_id).first()
        if not entity:
            return False
        
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("subjects", str(entity_id))
        self._delete_from_neo4j("Subject", str(entity_id))
        
        return True
    
    def get_subjects(self) -> List[Subject]:
        return self.pg_db.query(Subject).all()
    
    # ==================== Relationship ====================
    def create_relationship(self, data: Dict[str, Any]) -> Relationship:
        entity = Relationship(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("relationships", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "inverse_relationship": entity.inverse_relationship,
            "semantic_type": entity.semantic_type,
        })
        
        # Note: Relationships are typically edge types in Neo4j, not nodes
        # Store as node for reference, but actual relationships created separately
        self._sync_to_neo4j("RelationType", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
        })
        
        return entity
    
    def update_relationship(self, entity_id: int, data: Dict[str, Any]) -> Optional[Relationship]:
        entity = self.pg_db.query(Relationship).filter(Relationship.id == entity_id).first()
        if not entity:
            return None
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("relationships", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "inverse_relationship": entity.inverse_relationship,
            "semantic_type": entity.semantic_type,
        })
        
        self._sync_to_neo4j("RelationType", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
        })
        
        return entity
    
    def delete_relationship(self, entity_id: int) -> bool:
        entity = self.pg_db.query(Relationship).filter(Relationship.id == entity_id).first()
        if not entity:
            return False
        
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("relationships", str(entity_id))
        self._delete_from_neo4j("RelationType", str(entity_id))
        
        return True
    
    def get_relationships(self) -> List[Relationship]:
        return self.pg_db.query(Relationship).all()
    
    # ==================== Diagram ====================
    def create_diagram(self, data: Dict[str, Any]) -> Diagram:
        entity = Diagram(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("diagrams", entity.id, {
            "id": entity.id,
            "category_id": entity.category_id,
            "image_path": entity.image_path,
            "processed": entity.processed,
            "diagram_metadata": entity.diagram_metadata,
        })
        
        self._sync_to_neo4j("Diagram", entity.id, {
            "image_path": entity.image_path,
            "processed": entity.processed,
        })
        
        return entity
    
    def update_diagram(self, entity_id: str, data: Dict[str, Any]) -> Optional[Diagram]:
        entity = self.pg_db.query(Diagram).filter(Diagram.id == entity_id).first()
        if not entity:
            return None
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("diagrams", entity.id, {
            "id": entity.id,
            "category_id": entity.category_id,
            "image_path": entity.image_path,
            "processed": entity.processed,
            "diagram_metadata": entity.diagram_metadata,
        })
        
        self._sync_to_neo4j("Diagram", entity.id, {
            "image_path": entity.image_path,
            "processed": entity.processed,
        })
        
        return entity
    
    def delete_diagram(self, entity_id: str) -> bool:
        entity = self.pg_db.query(Diagram).filter(Diagram.id == entity_id).first()
        if not entity:
            return False
        
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("diagrams", entity_id)
        self._delete_from_neo4j("Diagram", entity_id)
        
        return True
    
    def get_diagrams(self) -> List[Diagram]:
        return self.pg_db.query(Diagram).all()
    
    # ==================== Subject-Relationship-Object ====================
    def create_triple(self, data: Dict[str, Any]) -> SubjectRelationshipObject:
        """Create a triple (subject-relationship-object) with Neo4j sync"""
        entity = SubjectRelationshipObject(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        # Get relationship name for Neo4j edge
        rel = self.pg_db.query(Relationship).filter(Relationship.id == entity.relationship_id).first()
        rel_name = rel.code.upper().replace(" ", "_") if rel else "RELATED_TO"
        
        # Create edge in Neo4j
        self._create_relationship_in_neo4j(
            str(entity.subject_id),
            rel_name,
            str(entity.object_id),
            {"confidence_score": float(entity.confidence_score) if entity.confidence_score else None}
        )
        
        # Store in MongoDB
        self._sync_to_mongo("subject_relationship_object", str(entity.id), {
            "id": entity.id,
            "subject_id": entity.subject_id,
            "relationship_id": entity.relationship_id,
            "object_id": entity.object_id,
            "diagram_id": entity.diagram_id,
            "confidence_score": float(entity.confidence_score) if entity.confidence_score else None,
            "context": entity.context,
        })
        
        return entity
    
    def get_triples(self) -> List[SubjectRelationshipObject]:
        return self.pg_db.query(SubjectRelationshipObject).all()
