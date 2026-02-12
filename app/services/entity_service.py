"""
Entity Management Service
Handles CRUD operations for all entities with tri-database synchronization
MongoDB, PostgreSQL, and Neo4j are kept in sync
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import re

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
        """Sync entity data to Neo4j (always match by name to avoid duplicates)"""
        session = get_neo4j_session()
        try:
            # Prepare properties for Neo4j (remove None values)
            props = {k: v for k, v in properties.items() if v is not None}
            
            # Always match by name (stable identifier across all nodes)
            name = props.get("name")
            if not name:
                return  # Skip if no name available
            
            # Create or update node - match by name, then set all properties including code
            query = f"""
            MERGE (n:{label} {{name: $name}})
            SET n += $props
            RETURN n
            """
            session.run(query, name=name, props=props)
        finally:
            session.close()
    
    def _delete_from_neo4j(self, label: str, entity_id: str, name: str = None):
        """Delete entity from Neo4j (match by name)"""
        session = get_neo4j_session()
        try:
            if name:
                query = f"MATCH (n:{label} {{name: $name}}) DETACH DELETE n"
                session.run(query, name=name)
            else:
                # Fallback: try to match by id if name not provided
                query = f"MATCH (n:{label} {{id: $id}}) DETACH DELETE n"
                session.run(query, id=entity_id)
        finally:
            session.close()

    def _ensure_root_node(self) -> None:
        session = get_neo4j_session()
        try:
            session.run(
                "MERGE (root:Root {name: $name})",
                name="AI2D_Knowledge_Graph"
            )
        finally:
            session.close()

    def _link_root_category(self, root_category_name: Optional[str]) -> None:
        if not root_category_name:
            return
        session = get_neo4j_session()
        try:
            query = """
            MATCH (rc:RootCategory {name: $rc_name})
            MERGE (root:Root {name: $root_name})
            MERGE (root)-[:HAS_ROOT_CATEGORY]->(rc)
            """
            session.run(
                query,
                root_name="AI2D_Knowledge_Graph",
                rc_name=root_category_name
            )
        finally:
            session.close()

    def _link_root_subject(self, root_subject_name: Optional[str]) -> None:
        if not root_subject_name:
            return
        session = get_neo4j_session()
        try:
            query = """
            MATCH (rs:RootSubject {name: $rs_name})
            MERGE (root:Root {name: $root_name})
            MERGE (root)-[:HAS_ROOT_SUBJECT]->(rs)
            """
            session.run(
                query,
                root_name="AI2D_Knowledge_Graph",
                rs_name=root_subject_name
            )
        finally:
            session.close()

    def _link_category_to_root(self, root_category_name: Optional[str], category_name: Optional[str], clear_existing: bool = False) -> None:
        if not category_name:
            return
        session = get_neo4j_session()
        try:
            if clear_existing:
                cleanup_query = """
                MATCH (c:Category {name: $category_name})
                OPTIONAL MATCH (rc:RootCategory)-[r:HAS_CATEGORY]->(c)
                DELETE r
                """
                session.run(cleanup_query, category_name=category_name)

            if not root_category_name:
                return

            link_query = """
            MATCH (rc:RootCategory {name: $root_category_name})
            MATCH (c:Category {name: $category_name})
            MERGE (rc)-[:HAS_CATEGORY]->(c)
            """
            session.run(
                link_query,
                root_category_name=root_category_name,
                category_name=category_name
            )
        finally:
            session.close()

    def _link_subject_to_root(self, root_subject_name: Optional[str], subject_name: Optional[str], clear_existing: bool = False) -> None:
        if not subject_name:
            return
        session = get_neo4j_session()
        try:
            if clear_existing:
                cleanup_query = """
                MATCH (s:Subject {name: $subject_name})
                OPTIONAL MATCH (rs:RootSubject)-[r:HAS_SUBJECT]->(s)
                DELETE r
                """
                session.run(cleanup_query, subject_name=subject_name)

            if not root_subject_name:
                return

            link_query = """
            MATCH (rs:RootSubject {name: $root_subject_name})
            MATCH (s:Subject {name: $subject_name})
            MERGE (rs)-[:HAS_SUBJECT]->(s)
            """
            session.run(
                link_query,
                root_subject_name=root_subject_name,
                subject_name=subject_name
            )
        finally:
            session.close()
    
    def _create_relationship_in_neo4j(self, subject_code: str, rel_name: str, object_code: str, properties: Dict = None):
        """Create relationship in Neo4j (match subjects by code or name)"""
        session = get_neo4j_session()
        try:
            props = properties or {}
            # Try to match by code first, fallback to id
            query = f"""
            MATCH (s:Subject)
            WHERE s.code = $subject_code OR s.id = $subject_code OR s.name = $subject_code
            MATCH (o:Subject)
            WHERE o.code = $object_code OR o.id = $object_code OR o.name = $object_code
            MERGE (s)-[r:{rel_name}]->(o)
            SET r += $props
            RETURN r
            """
            session.run(query, subject_code=str(subject_code), object_code=str(object_code), props=props)
        finally:
            session.close()

    def _derive_relationship_code(self, semantic_type: Optional[str], name: str) -> str:
        """
        Generate relationship code from semantic_type + name
        Example: semantic_type='trophic', name='eats' -> 'TRP-EATS'
        """
        if not name:
            return "UNK"
        
        # Clean and uppercase the name
        name_clean = re.sub(r"[^A-Za-z0-9]", "", name.strip()).upper()
        
        # If semantic_type is provided, use it as prefix
        if semantic_type:
            type_clean = re.sub(r"[^A-Za-z0-9]", "", semantic_type.strip()).upper()
            # Get first 3 letters of semantic type
            type_prefix = type_clean[:3] if len(type_clean) >= 3 else type_clean
            return f"{type_prefix}-{name_clean}"
        
        # If no semantic type, just return the clean name
        return name_clean


        if not raw_value:
            return "UNK"
        value = raw_value.strip()
        if re.fullmatch(r"[A-Z0-9_]{1,6}", value):
            return value
        parts = re.split(r"[^A-Za-z0-9]+", value)
        initials = "".join(part[0] for part in parts if part)
        if len(initials) >= 3:
            return initials.upper()
        compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
        if len(compact) >= 3:
            return compact[:3]
        return (compact + "XXX")[:3]

    def _next_subject_sequence(self, root_code: str) -> int:
        prefix = f"SUB-{root_code}-"
        existing_codes = (
            self.pg_db.query(Subject.code)
            .filter(Subject.code.like(f"{prefix}%"))
            .all()
        )
        max_seq = 0
        for (code,) in existing_codes:
            if not code or not code.startswith(prefix):
                continue
            suffix = code[len(prefix):]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
        return max_seq + 1
    
    # ==================== RootCategory ====================
    def create_root_category(self, data: Dict[str, Any]) -> RootCategory:
        # PostgreSQL
        if not data.get("code"):
            data["code"] = self._derive_root_code(data.get("id"))
        entity = RootCategory(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        # MongoDB
        self._sync_to_mongo("root_categories", entity.id, {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "created_at": entity.created_at,
        })
        
        # Neo4j
        self._sync_to_neo4j("RootCategory", entity.id, {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
        })
        self._ensure_root_node()
        self._link_root_category(entity.name)
        
        return entity
    
    def update_root_category(self, entity_id: str, data: Dict[str, Any]) -> Optional[RootCategory]:
        entity = self.pg_db.query(RootCategory).filter(RootCategory.id == entity_id).first()
        if not entity:
            return None

        if "code" not in data and not entity.code:
            data["code"] = self._derive_root_code(entity.id)
        
        # Update PostgreSQL
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        # Sync to MongoDB and Neo4j
        self._sync_to_mongo("root_categories", entity.id, {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
        })
        self._sync_to_neo4j("RootCategory", entity.id, {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
        })
        self._ensure_root_node()
        self._link_root_category(entity.name)
        
        return entity
    
    def delete_root_category(self, entity_id: str) -> bool:
        entity = self.pg_db.query(RootCategory).filter(RootCategory.id == entity_id).first()
        if not entity:
            return False
        
        entity_name = entity.name
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("root_categories", entity_id)
        self._delete_from_neo4j("RootCategory", entity_id, name=entity_name)
        
        return True
    
    def get_root_categories(self) -> List[RootCategory]:
        return self.pg_db.query(RootCategory).all()
    
    # ==================== Category ====================
    def create_category(self, data: Dict[str, Any]) -> Category:
        if not data.get("root_category_id"):
            raise ValueError("Root category not found")
        root = self.pg_db.query(RootCategory).filter(RootCategory.id == data.get("root_category_id")).first()
        if not root:
            raise ValueError("Root category not found")
        if not data.get("code"):
            root_code = root.code or self._derive_root_code(root.id)
            level = data.get("level") or 1
            data["code"] = f"CAT-{root_code}-{level}"
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
        self._link_category_to_root(root.name if root else None, entity.name, clear_existing=True)
        
        return entity
    
    def update_category(self, entity_id: int, data: Dict[str, Any]) -> Optional[Category]:
        entity = self.pg_db.query(Category).filter(Category.id == entity_id).first()
        if not entity:
            return None

        if "root_category_id" in data or "level" in data:
            root_category_id = data.get("root_category_id", entity.root_category_id)
            root = self.pg_db.query(RootCategory).filter(RootCategory.id == root_category_id).first()
            if not root:
                raise ValueError("Root category not found")
            root_code = root.code or self._derive_root_code(root.id)
            level = data.get("level", entity.level or 1)
            data["code"] = f"CAT-{root_code}-{level}"
        
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
        root = self.pg_db.query(RootCategory).filter(RootCategory.id == entity.root_category_id).first()
        self._link_category_to_root(root.name if root else None, entity.name, clear_existing=True)
        
        return entity
    
    def delete_category(self, entity_id: int) -> bool:
        entity = self.pg_db.query(Category).filter(Category.id == entity_id).first()
        if not entity:
            return False
        
        entity_name = entity.name
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("categories", str(entity_id))
        self._delete_from_neo4j("Category", str(entity_id), name=entity_name)
        
        return True
    
    def get_categories(self) -> List[Category]:
        return self.pg_db.query(Category).all()
    
    # ==================== RootSubject ====================
    def create_root_subject(self, data: Dict[str, Any]) -> RootSubject:
        if not data.get("code"):
            data["code"] = self._derive_root_code(data.get("name"))
        entity = RootSubject(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("root_subjects", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "parent_id": entity.parent_id,
            "level": entity.level,
        })
        
        self._sync_to_neo4j("RootSubject", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "level": entity.level,
        })
        self._ensure_root_node()
        self._link_root_subject(entity.name)
        
        return entity
    
    def update_root_subject(self, entity_id: int, data: Dict[str, Any]) -> Optional[RootSubject]:
        entity = self.pg_db.query(RootSubject).filter(RootSubject.id == entity_id).first()
        if not entity:
            return None

        if "code" not in data and "name" in data:
            data["code"] = self._derive_root_code(data.get("name"))
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        self._sync_to_mongo("root_subjects", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "parent_id": entity.parent_id,
            "level": entity.level,
        })
        
        self._sync_to_neo4j("RootSubject", str(entity.id), {
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "level": entity.level,
        })
        self._ensure_root_node()
        self._link_root_subject(entity.name)
        
        return entity
    
    def delete_root_subject(self, entity_id: int) -> bool:
        entity = self.pg_db.query(RootSubject).filter(RootSubject.id == entity_id).first()
        if not entity:
            return False
        
        entity_name = entity.name
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("root_subjects", str(entity_id))
        self._delete_from_neo4j("RootSubject", str(entity_id), name=entity_name)
        
        return True
    
    def get_root_subjects(self) -> List[RootSubject]:
        return self.pg_db.query(RootSubject).all()
    
    # ==================== Subject ====================
    def create_subject(self, data: Dict[str, Any]) -> Subject:
        if not data.get("root_subject_id"):
            raise ValueError("Root subject not found")
        root = self.pg_db.query(RootSubject).filter(RootSubject.id == data.get("root_subject_id")).first()
        if not root:
            raise ValueError("Root subject not found")
        if not data.get("code"):
            root_code = root.code or self._derive_root_code(root.name)
            seq = self._next_subject_sequence(root_code)
            data["code"] = f"SUB-{root_code}-{seq:03d}"
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
        self._link_subject_to_root(root.name if root else None, entity.name, clear_existing=True)
        
        return entity
    
    def update_subject(self, entity_id: int, data: Dict[str, Any]) -> Optional[Subject]:
        entity = self.pg_db.query(Subject).filter(Subject.id == entity_id).first()
        if not entity:
            return None

        if "root_subject_id" in data:
            root = self.pg_db.query(RootSubject).filter(RootSubject.id == data.get("root_subject_id")).first()
            if not root:
                raise ValueError("Root subject not found")
            root_code = root.code or self._derive_root_code(root.name)
            seq = self._next_subject_sequence(root_code)
            data["code"] = f"SUB-{root_code}-{seq:03d}"
        
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
        root = self.pg_db.query(RootSubject).filter(RootSubject.id == entity.root_subject_id).first()
        self._link_subject_to_root(root.name if root else None, entity.name, clear_existing=True)
        
        return entity
    
    def delete_subject(self, entity_id: int) -> bool:
        entity = self.pg_db.query(Subject).filter(Subject.id == entity_id).first()
        if not entity:
            return False
        
        entity_name = entity.name
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        self._delete_from_mongo("subjects", str(entity_id))
        self._delete_from_neo4j("Subject", str(entity_id), name=entity_name)
        
        return True
    
    def get_subjects(self) -> List[Subject]:
        return self.pg_db.query(Subject).all()
    
    # ==================== Relationship ====================
    def create_relationship(self, data: Dict[str, Any]) -> Relationship:
        # Auto-generate code if not provided
        if not data.get('code'):
            data['code'] = self._derive_relationship_code(
                data.get('semantic_type'),
                data.get('name')
            )
        
        entity = Relationship(**data)
        self.pg_db.add(entity)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        # Sync to MongoDB only (not Neo4j)
        # Relationships in Neo4j are only created as edges when SROs are created
        self._sync_to_mongo("relationships", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "inverse_relationship": entity.inverse_relationship,
            "semantic_type": entity.semantic_type,
        })
        
        return entity
    
    def update_relationship(self, entity_id: int, data: Dict[str, Any]) -> Optional[Relationship]:
        entity = self.pg_db.query(Relationship).filter(Relationship.id == entity_id).first()
        if not entity:
            return None
        
        # Auto-update code if name or semantic_type changed
        if 'name' in data or 'semantic_type' in data:
            new_semantic_type = data.get('semantic_type', entity.semantic_type)
            new_name = data.get('name', entity.name)
            # Always regenerate code when name or semantic_type changes
            data['code'] = self._derive_relationship_code(new_semantic_type, new_name)
        
        for key, value in data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.pg_db.commit()
        self.pg_db.refresh(entity)
        
        # Sync to MongoDB only (not Neo4j)
        # Relationships in Neo4j are only created as edges when SROs are created
        self._sync_to_mongo("relationships", str(entity.id), {
            "id": entity.id,
            "code": entity.code,
            "name": entity.name,
            "description": entity.description,
            "inverse_relationship": entity.inverse_relationship,
            "semantic_type": entity.semantic_type,
        })
        
        return entity
    
    def delete_relationship(self, entity_id: int) -> bool:
        entity = self.pg_db.query(Relationship).filter(Relationship.id == entity_id).first()
        if not entity:
            return False
        
        self.pg_db.delete(entity)
        self.pg_db.commit()
        
        # Delete from MongoDB only
        # Relationships don't exist as nodes in Neo4j (only as edges in SRO)
        self._delete_from_mongo("relationships", str(entity_id))
        
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
        self._delete_from_neo4j("Diagram", entity_id, name=entity_id)
        
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
        rel_name = rel.code.upper().replace(" ", "_") if rel and rel.code else "RELATED_TO"
        
        # Get subject and object codes/names
        subject = self.pg_db.query(Subject).filter(Subject.id == entity.subject_id).first()
        obj = self.pg_db.query(Subject).filter(Subject.id == entity.object_id).first()
        subject_match = subject.code if subject and subject.code else (subject.name if subject else str(entity.subject_id))
        object_match = obj.code if obj and obj.code else (obj.name if obj else str(entity.object_id))
        
        # Create edge in Neo4j
        self._create_relationship_in_neo4j(
            subject_match,
            rel_name,
            object_match,
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
