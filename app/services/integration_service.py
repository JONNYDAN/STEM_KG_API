from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from app.services.postgres_service import PostgresService
from app.services.neo4j_service import Neo4jService
from app.services.mongo_service import MongoService

logger = logging.getLogger(__name__)

class IntegrationService:
    def __init__(
        self,
        postgres_db: Session,
        neo4j_driver = None,
        mongo_db = None
    ):
        self.postgres_service = PostgresService(postgres_db)
        self.mongo_service = MongoService(mongo_db) if mongo_db else None
        self.neo4j_driver = neo4j_driver
    
    async def process_triple_query(
        self, 
        subject: str, 
        relationship: str, 
        object: str
    ) -> Dict[str, Any]:
        """
        Process a triple query across all three databases
        
        Flow based on your requirements:
        1. Try to find matching category from triple
        2. If found, get diagrams from that category
        3. If not, use subject and object root subjects to infer category
        """
        
        results = {
            "query": {"subject": subject, "relationship": relationship, "object": object},
            "timestamp": datetime.utcnow().isoformat(),
            "postgres": [],
            "neo4j": [],
            "mongo": []
        }
        
        # Step 1: Search in PostgreSQL for category matching
        try:
            pg_results = await self.postgres_service.search_categories_by_triple(
                subject, relationship, object
            )
            results["postgres"] = pg_results
            
            # If we found categories, get diagrams for the best match
            if pg_results:
                best_category = pg_results[0]  # Highest relevance score
                
                # Get diagrams from PostgreSQL
                category_obj = await self.postgres_service.get_category(best_category["id"])
                if category_obj:
                    diagrams = await self.postgres_service.get_diagrams_by_category(category_obj.id)
                    results["postgres_diagrams"] = [dict(d) for d in diagrams]
        
        except Exception as e:
            logger.error(f"PostgreSQL query error: {e}")
            results["postgres_error"] = str(e)
        
        # Step 2: Search in Neo4j for matching diagrams
        try:
            async with self.neo4j_driver.session() as session:
                neo4j_service = Neo4jService(session)
                neo4j_results = await neo4j_service.search_diagrams_by_triple(
                    subject, relationship, object
                )
                results["neo4j"] = neo4j_results
        except Exception as e:
            logger.error(f"Neo4j query error: {e}")
            results["neo4j_error"] = str(e)
        
        # Step 3: Search in MongoDB for annotations
        try:
            # Get diagram IDs from Neo4j results
            diagram_ids = [r["diagram_id"] for r in results.get("neo4j", [])]
            
            if diagram_ids:
                mongo_results = await self.mongo_service.get_annotations_by_diagrams(diagram_ids)
                results["mongo"] = mongo_results
        except Exception as e:
            logger.error(f"MongoDB query error: {e}")
            results["mongo_error"] = str(e)
        
        # Step 4: If no direct category found, infer from subject/object root subjects
        if not results["postgres"] and not results["neo4j"]:
            inferred_category = await self._infer_category_from_root_subjects(subject, object)
            if inferred_category:
                results["inferred_category"] = inferred_category
                
                # Get diagrams for inferred category
                async with self.neo4j_driver.session() as session:
                    neo4j_service = Neo4jService(session)
                    query = """
                    MATCH (d:Diagram {category: $category})
                    RETURN d
                    """
                    result = await session.run(query, category=inferred_category)
                    results["inferred_diagrams"] = [dict(record["d"]) for record in await result.data()]
        
        return results
    
    async def _infer_category_from_root_subjects(
        self, 
        subject: str, 
        object: str
    ) -> Optional[str]:
        """
        Infer category based on root subjects of subject and object
        Example: "bee" (insect) + "flower" (plant) -> "foodChainsWebs"
        """
        try:
            # Get subject from PostgreSQL
            subject_obj = await self.postgres_service.get_subject_by_name(subject)
            object_obj = await self.postgres_service.get_subject_by_name(object)
            
            if subject_obj and object_obj:
                # Simple inference logic - can be enhanced
                subject_type = subject_obj.root_subject.name.lower()
                object_type = object_obj.root_subject.name.lower()
                
                # Inference rules
                if ("insect" in subject_type or "animal" in subject_type) and \
                   ("plant" in object_type or "flower" in object_type):
                    return "foodChainsWebs"
                elif ("animal" in subject_type) and ("animal" in object_type):
                    return "foodChainsWebs"
                elif ("plant" in subject_type) and ("plant" in object_type):
                    return "lifeCycles"
                elif ("earth" in subject_type or "earth" in object_type):
                    return "partsOfTheEarth"
            
            return None
            
        except Exception as e:
            logger.error(f"Category inference error: {e}")
            return None
    
    async def sync_diagram(self, diagram_id: str) -> Dict[str, Any]:
        """Sync a diagram across all three databases"""
        sync_result = {
            "diagram_id": diagram_id,
            "postgres": False,
            "neo4j": False,
            "mongodb": False,
            "errors": []
        }
        
        # Get diagram from PostgreSQL (source of truth)
        diagram = await self.postgres_service.get_diagram(diagram_id)
        if not diagram:
            sync_result["errors"].append("Diagram not found in PostgreSQL")
            return sync_result
        
        # Sync to Neo4j
        try:
            async with self.neo4j_driver.session() as session:
                neo4j_service = Neo4jService(session)
                
                # Check if exists in Neo4j
                query = "MATCH (d:Diagram {id: $id}) RETURN d"
                result = await session.run(query, id=diagram_id)
                existing = await result.single()
                
                if existing:
                    # Update existing
                    await neo4j_service.update_diagram_node(
                        diagram_id,
                        {
                            "category": diagram.category.name,
                            "image_path": diagram.image_path,
                            "processed": diagram.processed
                        }
                    )
                else:
                    # Create new
                    await neo4j_service.create_diagram_node(
                        {
                            "id": diagram_id,
                            "category": diagram.category.name,
                            "image_path": diagram.image_path,
                            "processed": diagram.processed
                        }
                    )
                
                sync_result["neo4j"] = True
                
        except Exception as e:
            sync_result["errors"].append(f"Neo4j sync error: {str(e)}")
        
        # Sync to MongoDB
        try:
            # Check if annotations exist
            existing_annotation = await self.mongo_service.get_diagram_annotation(diagram_id)
            
            if not existing_annotation:
                # Create basic annotation entry
                await self.mongo_service.create_diagram_annotation({
                    "diagram_id": diagram_id,
                    "category": diagram.category.name,
                    "annotations": {},
                    "metadata": {
                        "synced_from_postgres": True,
                        "sync_timestamp": datetime.utcnow().isoformat()
                    }
                })
            
            sync_result["mongodb"] = True
            
        except Exception as e:
            sync_result["errors"].append(f"MongoDB sync error: {str(e)}")
        
        sync_result["postgres"] = True
        return sync_result
    
    async def bulk_import(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk import data into all databases"""
        statistics = {
            "total_records": 0,
            "postgres_inserted": 0,
            "neo4j_inserted": 0,
            "mongodb_inserted": 0,
            "errors": []
        }
        
        # Process diagrams
        diagrams = data.get("diagrams", [])
        statistics["total_records"] = len(diagrams)
        
        for diagram_data in diagrams:
            try:
                # Import to PostgreSQL
                diagram_create = DiagramCreate(**diagram_data)
                await self.postgres_service.create_diagram(diagram_create)
                statistics["postgres_inserted"] += 1
                
                # Import to Neo4j
                async with self.neo4j_driver.session() as session:
                    neo4j_service = Neo4jService(session)
                    await neo4j_service.create_diagram_node({
                        "id": diagram_data["id"],
                        "category": diagram_data.get("category", ""),
                        "image_path": diagram_data.get("image_path", ""),
                        "processed": diagram_data.get("processed", False)
                    })
                    statistics["neo4j_inserted"] += 1
                
                # Import to MongoDB
                await self.mongo_service.create_diagram_annotation({
                    "diagram_id": diagram_data["id"],
                    "category": diagram_data.get("category", ""),
                    "annotations": {},
                    "metadata": diagram_data.get("metadata", {})
                })
                statistics["mongodb_inserted"] += 1
                
            except Exception as e:
                statistics["errors"].append({
                    "diagram_id": diagram_data.get("id", "unknown"),
                    "error": str(e)
                })
        
        return statistics
    
    def create_sro_synced(
        self,
        subject_id: int,
        relationship_id: int,
        object_id: int,
        diagram_id: Optional[str] = None,
        confidence_score: Optional[float] = None,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Subject-Relationship-Object triple and sync to both PostgreSQL and Neo4j
        Auto-generate code as S + R + O codes
        """
        result = {
            "success": False,
            "postgres": None,
            "neo4j": None,
            "code": None,
            "errors": []
        }
        
        try:
            # Get subject, relationship, object details from PostgreSQL
            subject = self.postgres_service.get_subject(subject_id)
            relationship = self.postgres_service.get_relationship(relationship_id)
            obj = self.postgres_service.get_subject(object_id)
            
            if not subject or not relationship or not obj:
                result["errors"].append("Subject, Relationship, or Object not found")
                return result
            
            # Generate code: S + R + O
            sro_code = f"{subject.code}_{relationship.code}_{obj.code}"
            result["code"] = sro_code
            
            # 1. Create in PostgreSQL
            from app.schemas.postgres_schemas import SROCreate
            sro_data = SROCreate(
                subject_id=subject_id,
                relationship_id=relationship_id,
                object_id=object_id,
                diagram_id=diagram_id,
                confidence_score=confidence_score,
                context=context
            )
            
            # Check if already exists
            existing_sro = self.postgres_service.get_sro_by_triple(
                subject_id, relationship_id, object_id
            )
            
            if existing_sro:
                result["postgres"] = {"id": existing_sro.id, "status": "already_exists"}
            else:
                pg_sro = self.postgres_service.create_sro(sro_data)
                result["postgres"] = {"id": pg_sro.id, "status": "created"}
            
            # 2. Create in Neo4j
            if self.neo4j_driver:
                neo4j_service = Neo4jService()
                
                # Create relationship between subject and object nodes
                neo4j_result = neo4j_service.create_subject_relationship(
                    from_subject_id=subject_id,
                    to_subject_id=object_id,
                    relationship_type=relationship.name.upper().replace(" ", "_"),
                    properties={
                        "code": sro_code,
                        "confidence_score": confidence_score or 1.0,
                        "context": context or "",
                        "diagram_id": diagram_id or ""
                    }
                )
                result["neo4j"] = {"status": "created", "data": neo4j_result}
            
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Error creating synced SRO: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def update_sro_synced(
        self,
        sro_id: int,
        subject_id: Optional[int] = None,
        relationship_id: Optional[int] = None,
        object_id: Optional[int] = None,
        diagram_id: Optional[str] = None,
        confidence_score: Optional[float] = None,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update Subject-Relationship-Object triple in both PostgreSQL and Neo4j
        """
        result = {
            "success": False,
            "postgres": None,
            "neo4j": None,
            "errors": []
        }
        
        try:
            # Get existing SRO
            existing_sro = self.postgres_service.get_sro(sro_id)
            if not existing_sro:
                result["errors"].append("SRO not found")
                return result
            
            # Prepare update data
            from app.schemas.postgres_schemas import SROUpdate
            update_data = SROUpdate(
                subject_id=subject_id,
                relationship_id=relationship_id,
                object_id=object_id,
                diagram_id=diagram_id,
                confidence_score=confidence_score,
                context=context
            )
            
            # Get old triple info for Neo4j deletion
            old_subject = self.postgres_service.get_subject(existing_sro.subject_id)
            old_relationship = self.postgres_service.get_relationship(existing_sro.relationship_id)
            old_object = self.postgres_service.get_subject(existing_sro.object_id)
            
            # 1. Update in PostgreSQL
            updated_sro = self.postgres_service.update_sro(sro_id, update_data)
            result["postgres"] = {"id": updated_sro.id, "status": "updated"}
            
            # 2. Update in Neo4j (delete old, create new if triple changed)
            if self.neo4j_driver and (subject_id or relationship_id or object_id):
                neo4j_service = Neo4jService()
                
                # If subject, relationship, or object changed, delete old relationship
                old_rel_type = old_relationship.name.upper().replace(" ", "_")
                neo4j_service.delete_relationship_between_subjects(
                    old_subject.id, old_object.id, old_rel_type
                )
                
                # Create new relationship
                new_subject = self.postgres_service.get_subject(
                    subject_id or existing_sro.subject_id
                )
                new_relationship = self.postgres_service.get_relationship(
                    relationship_id or existing_sro.relationship_id
                )
                new_object = self.postgres_service.get_subject(
                    object_id or existing_sro.object_id
                )
                
                new_code = f"{new_subject.code}_{new_relationship.code}_{new_object.code}"
                
                neo4j_service.create_subject_relationship(
                    from_subject_id=new_subject.id,
                    to_subject_id=new_object.id,
                    relationship_type=new_relationship.name.upper().replace(" ", "_"),
                    properties={
                        "code": new_code,
                        "confidence_score": confidence_score or updated_sro.confidence_score or 1.0,
                        "context": context or updated_sro.context or "",
                        "diagram_id": diagram_id or updated_sro.diagram_id or ""
                    }
                )
                
                result["neo4j"] = {"status": "updated"}
            
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Error updating synced SRO: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def delete_sro_synced(self, sro_id: int) -> Dict[str, Any]:
        """
        Delete Subject-Relationship-Object triple from both PostgreSQL and Neo4j
        """
        result = {
            "success": False,
            "postgres": None,
            "neo4j": None,
            "errors": []
        }
        
        try:
            # Get existing SRO for Neo4j deletion
            existing_sro = self.postgres_service.get_sro(sro_id)
            if not existing_sro:
                result["errors"].append("SRO not found")
                return result
            
            subject = self.postgres_service.get_subject(existing_sro.subject_id)
            relationship = self.postgres_service.get_relationship(existing_sro.relationship_id)
            obj = self.postgres_service.get_subject(existing_sro.object_id)
            
            # 1. Delete from Neo4j first
            if self.neo4j_driver:
                neo4j_service = Neo4jService()
                rel_type = relationship.name.upper().replace(" ", "_")
                neo4j_service.delete_relationship_between_subjects(
                    subject.id, obj.id, rel_type
                )
                result["neo4j"] = {"status": "deleted"}
            
            # 2. Delete from PostgreSQL
            deleted = self.postgres_service.delete_sro(sro_id)
            result["postgres"] = {"status": "deleted" if deleted else "not_found"}
            
            result["success"] = deleted
            
        except Exception as e:
            logger.error(f"Error deleting synced SRO: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def get_all_sros_with_details(
        self,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all SROs with full details (subject name, relationship name, object name)
        """
        try:
            sros = self.postgres_service.get_all_sros(skip=skip, limit=limit)
            
            result = []
            for sro in sros:
                subject = self.postgres_service.get_subject(sro.subject_id)
                relationship = self.postgres_service.get_relationship(sro.relationship_id)
                obj = self.postgres_service.get_subject(sro.object_id)
                
                code = f"{subject.code}_{relationship.code}_{obj.code}"
                
                result.append({
                    "id": sro.id,
                    "code": code,
                    "subject_id": sro.subject_id,
                    "subject_name": subject.name,
                    "subject_code": subject.code,
                    "relationship_id": sro.relationship_id,
                    "relationship_name": relationship.name,
                    "relationship_code": relationship.code,
                    "object_id": sro.object_id,
                    "object_name": obj.name,
                    "object_code": obj.code,
                    "diagram_id": sro.diagram_id,
                    "confidence_score": float(sro.confidence_score) if sro.confidence_score else None,
                    "context": sro.context,
                    "created_at": sro.created_at.isoformat() if sro.created_at else None
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting SROs with details: {e}")
            return []