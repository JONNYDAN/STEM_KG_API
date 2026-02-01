# app/routes/neo4j_routes.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.neo4j_service import Neo4jService
from app.schemas.neo4j_schemas import NodeCreate, RelationshipCreate, NodeUpdateByKey
from app.schemas import postgres_schemas as pg_schemas
from app.database.postgres_conn import get_postgres_db
from app.services.postgres_service import PostgresService
from app.services.mongo_service import MongoService
from app.schemas import mongo_schemas as mongo_schemas

router = APIRouter(prefix="/neo4j", tags=["Neo4j"])

@router.post("/nodes/", response_model=Dict[str, Any])
def create_node(node_data: NodeCreate):
    """Tạo node mới trong Neo4j"""
    service = Neo4jService()
    try:
        result = service.create_node(node_data)
        return {"success": True, "node": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.post("/relationships/", response_model=Dict[str, Any])
def create_relationship(rel_data: RelationshipCreate):
    """Tạo relationship giữa các node"""
    service = Neo4jService()
    try:
        result = service.create_relationship(rel_data)
        return {"success": True, "relationship": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.get("/nodes/", response_model=List[Dict[str, Any]])
def get_all_nodes(limit: int = 100, label: str = None):
    """Lấy tất cả nodes (tuỳ chọn theo label)"""
    service = Neo4jService()
    try:
        nodes = service.get_all_nodes(limit, label)
        return nodes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.get("/nodes/{node_id}", response_model=Dict[str, Any])
def get_node(node_id: str):
    """Lấy node bằng ID"""
    service = Neo4jService()
    try:
        node = service.get_node_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.get("/nodes/by-key", response_model=Dict[str, Any])
def get_node_by_key(label: str, key: str, value: str):
    """Lấy node theo label + key + value"""
    service = Neo4jService()
    try:
        node = service.get_node_by_key(label, key, value)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.put("/nodes/{node_id}", response_model=Dict[str, Any])
def update_node(node_id: str, properties: Dict[str, Any]):
    """Cập nhật node"""
    service = Neo4jService()
    try:
        node = service.update_node(node_id, properties)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return {"success": True, "node": node}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.put("/nodes/by-key", response_model=Dict[str, Any])
def update_node_by_key(payload: NodeUpdateByKey):
    """Cập nhật node theo label + key + value"""
    service = Neo4jService()
    try:
        node = service.update_node_by_key(
            payload.selector.label,
            payload.selector.key,
            payload.selector.value,
            payload.properties
        )
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return {"success": True, "node": node}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    """Xóa node"""
    service = Neo4jService()
    try:
        success = service.delete_node(node_id)
        if not success:
            raise HTTPException(status_code=404, detail="Node not found")
        return {"success": True, "message": "Node deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.delete("/nodes/by-key")
def delete_node_by_key(label: str, key: str, value: str):
    """Xóa node theo label + key + value"""
    service = Neo4jService()
    try:
        success = service.delete_node_by_key(label, key, value)
        if not success:
            raise HTTPException(status_code=404, detail="Node not found")
        return {"success": True, "message": "Node deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

@router.get("/search/triple")
def search_by_triple(
    subject: str,
    relationship: str,
    object: str,
    subject_label: str = None,
    object_label: str = None,
    relationship_type: str = None
) -> List[Dict[str, Any]]:
    """Tìm kiếm bằng bộ ba"""
    service = Neo4jService()
    try:
        results = service.search_diagrams_by_triple(
            subject,
            relationship,
            object,
            subject_label=subject_label,
            object_label=object_label,
            relationship_type=relationship_type
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()

# ========== ROOT SUBJECTS (SYNC) ==========
@router.post("/root-subjects/", response_model=Dict[str, Any])
def create_root_subject_sync(
    root_subject: pg_schemas.RootSubjectCreate,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    try:
        # PostgreSQL service now handles upsert automatically
        pg_root = pg_service.create_root_subject(root_subject)
        
        # Determine action based on whether id was provided
        action = "updated" if hasattr(root_subject, 'id') and root_subject.id else "created"

        neo4j_node = neo4j_service.create_root_subject({
            "id": pg_root.id,
            "name": pg_root.name,
            "description": pg_root.description,
            "parent_id": pg_root.parent_id,
            "level": pg_root.level
        })
        # Log the actual result for debugging
        print(f"[DEBUG] Neo4j create_root_subject returned: {neo4j_node}")
        if not neo4j_node:
            print(f"[ERROR] Neo4j root subject creation returned None")
            return {
                "success": False,
                "error": "Neo4j root subject creation failed - returned None",
                "action": action,
                "postgres": pg_root.to_dict() if hasattr(pg_root, 'to_dict') else pg_root.__dict__,
                "neo4j": None,
                "mongo": None
            }

        mongo_doc = mongo_service.create_root_subject(
            root_subject=mongo_schemas.RootSubjectDocCreate(
                root_subject_id=pg_root.id,
                name=pg_root.name,
                description=pg_root.description,
                parent_id=pg_root.parent_id,
                level=pg_root.level
            )
        )
        if not mongo_doc:
            raise Exception("Mongo root subject creation failed")

        return {
            "success": True,
            "action": action,
            "postgres": pg_schemas.RootSubjectResponse.model_validate(pg_root).model_dump(),
            "neo4j": neo4j_node,
            "mongo": mongo_doc
        }
    except Exception as e:
        # rollback best-effort
        try:
            if "pg_root" in locals() and pg_root and action == "created":
                pg_service.delete_root_subject(pg_root.id)
        except Exception:
            pass
        try:
            if "neo4j_node" in locals() and neo4j_node:
                neo4j_service.delete_root_subject(pg_root.id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

@router.get("/root-subjects/{root_subject_id}", response_model=Dict[str, Any])
def get_root_subject_sync(
    root_subject_id: int,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    try:
        pg_root = pg_service.get_root_subject(root_subject_id)
        neo4j_root = neo4j_service.get_root_subject(root_subject_id)
        mongo_root = mongo_service.get_root_subject_by_root_id(root_subject_id)

        if not pg_root and not neo4j_root and not mongo_root:
            raise HTTPException(status_code=404, detail="Root subject not found")

        return {
            "postgres": pg_schemas.RootSubjectResponse.model_validate(pg_root).model_dump() if pg_root else None,
            "neo4j": neo4j_root,
            "mongo": mongo_root
        }
    finally:
        neo4j_service.close()

@router.put("/root-subjects/{root_subject_id}", response_model=Dict[str, Any])
def update_root_subject_sync(
    root_subject_id: int,
    root_subject_update: pg_schemas.RootSubjectUpdate,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    old_pg = pg_service.get_root_subject(root_subject_id)
    if not old_pg:
        neo4j_service.close()
        raise HTTPException(status_code=404, detail="Root subject not found")

    update_data = root_subject_update.model_dump(exclude_unset=True)
    try:
        pg_updated = pg_service.update_root_subject(root_subject_id, root_subject_update)
        neo4j_updated = neo4j_service.update_root_subject(root_subject_id, update_data)
        mongo_updated = mongo_service.update_root_subject(root_subject_id, update_data)

        if not neo4j_updated:
            raise Exception("Neo4j root subject update failed")

        return {
            "success": True,
            "postgres": pg_schemas.RootSubjectResponse.model_validate(pg_updated).model_dump() if pg_updated else None,
            "neo4j": neo4j_updated,
            "mongo": mongo_updated
        }
    except Exception as e:
        # rollback best-effort
        rollback_data = {
            "name": old_pg.name,
            "description": old_pg.description,
            "parent_id": old_pg.parent_id,
            "level": old_pg.level
        }
        try:
            pg_service.update_root_subject(root_subject_id, pg_schemas.RootSubjectUpdate(**rollback_data))
        except Exception:
            pass
        try:
            neo4j_service.update_root_subject(root_subject_id, rollback_data)
        except Exception:
            pass
        try:
            mongo_service.update_root_subject(root_subject_id, rollback_data)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

@router.delete("/root-subjects/{root_subject_id}")
def delete_root_subject_sync(
    root_subject_id: int,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    try:
        # Delete from Neo4j first (including all related subjects)
        if not neo4j_service.delete_root_subject(root_subject_id):
            raise Exception("Neo4j root subject delete failed")
        
        # Delete from MongoDB
        if not mongo_service.delete_root_subject(root_subject_id):
            raise Exception("Mongo root subject delete failed")
        # Delete from PostgreSQL (this also deletes related subjects)
        if not pg_service.delete_root_subject(root_subject_id):
            raise Exception("PostgreSQL root subject delete failed")

        return {"success": True, "message": "Root subject deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

# ========== SUBJECTS (SYNC) ==========
@router.post("/subjects/", response_model=Dict[str, Any])
def create_subject_sync(
    subject: pg_schemas.SubjectCreate,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    try:
        # PostgreSQL service now handles upsert automatically
        pg_subject = pg_service.create_subject(subject)
        
        # Determine action based on whether id was provided
        action = "updated" if hasattr(subject, 'id') and subject.id else "created"

        neo4j_node = neo4j_service.create_subject({
            "id": pg_subject.id,
            "name": pg_subject.name,
            "root_subject_id": pg_subject.root_subject_id,
            "synonyms": pg_subject.synonyms or [],
            "description": pg_subject.description,
            "categories": pg_subject.categories or []
        })
        if not neo4j_node:
            raise Exception("Neo4j subject creation failed")

        mongo_doc = mongo_service.create_subject(
            subject=mongo_schemas.SubjectDocCreate(
                subject_id=pg_subject.id,
                name=pg_subject.name,
                root_subject_id=pg_subject.root_subject_id,
                synonyms=pg_subject.synonyms or [],
                description=pg_subject.description,
                categories=pg_subject.categories or []
            )
        )
        if not mongo_doc:
            raise Exception("Mongo subject creation failed")

        return {
            "success": True,
            "action": action,
            "postgres": pg_schemas.SubjectResponse.model_validate(pg_subject).model_dump(),
            "neo4j": neo4j_node,
            "mongo": mongo_doc
        }
    except Exception as e:
        # rollback best-effort
        try:
            if "pg_subject" in locals() and pg_subject and action == "created":
                pg_service.delete_subject(pg_subject.id)
        except Exception:
            pass
        try:
            if "neo4j_node" in locals() and neo4j_node:
                neo4j_service.delete_subject(pg_subject.id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

@router.get("/subjects/{subject_id}", response_model=Dict[str, Any])
def get_subject_sync(
    subject_id: int,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    try:
        pg_subject = pg_service.get_subject(subject_id)
        neo4j_subject = neo4j_service.get_subject(subject_id)
        mongo_subject = mongo_service.get_subject_by_subject_id(subject_id)

        if not pg_subject and not neo4j_subject and not mongo_subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        return {
            "postgres": pg_schemas.SubjectResponse.model_validate(pg_subject).model_dump() if pg_subject else None,
            "neo4j": neo4j_subject,
            "mongo": mongo_subject
        }
    finally:
        neo4j_service.close()

@router.put("/subjects/{subject_id}", response_model=Dict[str, Any])
def update_subject_sync(
    subject_id: int,
    subject_update: pg_schemas.SubjectUpdate,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    old_pg = pg_service.get_subject(subject_id)
    if not old_pg:
        neo4j_service.close()
        raise HTTPException(status_code=404, detail="Subject not found")

    update_data = subject_update.model_dump(exclude_unset=True)
    try:
        pg_updated = pg_service.update_subject(subject_id, subject_update)
        neo4j_updated = neo4j_service.update_subject(subject_id, update_data)
        mongo_updated = mongo_service.update_subject(subject_id, update_data)

        if not neo4j_updated:
            raise Exception("Neo4j subject update failed")

        return {
            "success": True,
            "postgres": pg_schemas.SubjectResponse.model_validate(pg_updated).model_dump() if pg_updated else None,
            "neo4j": neo4j_updated,
            "mongo": mongo_updated
        }
    except Exception as e:
        rollback_data = {
            "name": old_pg.name,
            "root_subject_id": old_pg.root_subject_id,
            "synonyms": old_pg.synonyms or [],
            "description": old_pg.description
        }
        try:
            pg_service.update_subject(subject_id, pg_schemas.SubjectUpdate(**rollback_data))
        except Exception:
            pass
        try:
            neo4j_service.update_subject(subject_id, rollback_data)
        except Exception:
            pass
        try:
            mongo_service.update_subject(subject_id, rollback_data)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

@router.delete("/subjects/{subject_id}")
def delete_subject_sync(
    subject_id: int,
    db: Session = Depends(get_postgres_db)
):
    pg_service = PostgresService(db)
    neo4j_service = Neo4jService()
    mongo_service = MongoService()

    old_pg = pg_service.get_subject(subject_id)
    if not old_pg:
        neo4j_service.close()
        raise HTTPException(status_code=404, detail="Subject not found")

    try:
        if not neo4j_service.delete_subject(subject_id):
            raise Exception("Neo4j subject delete failed")
        if not mongo_service.delete_subject(subject_id):
            raise Exception("Mongo subject delete failed")

        if not pg_service.delete_subject(subject_id):
            neo4j_service.create_subject({
                "id": old_pg.id,
                "name": old_pg.name,
                "root_subject_id": old_pg.root_subject_id,
                "synonyms": old_pg.synonyms or [],
                "description": old_pg.description,
                "categories": old_pg.categories or []
            })
            mongo_service.create_subject(
                subject=mongo_schemas.SubjectDocCreate(
                    subject_id=old_pg.id,
                    name=old_pg.name,
                    root_subject_id=old_pg.root_subject_id,
                    synonyms=old_pg.synonyms or [],
                    description=old_pg.description,
                    categories=old_pg.categories or []
                )
            )
            raise HTTPException(status_code=500, detail="Failed to delete subject in PostgreSQL")

        return {"success": True, "message": "Subject deleted"}
    except Exception as e:
        # rollback if neo4j or mongo delete failed after changes
        try:
            if not neo4j_service.get_subject(old_pg.id):
                neo4j_service.create_subject({
                    "id": old_pg.id,
                    "name": old_pg.name,
                    "root_subject_id": old_pg.root_subject_id,
                    "synonyms": old_pg.synonyms or [],
                    "description": old_pg.description,
                    "categories": old_pg.categories or []
                })
        except Exception:
            pass
        try:
            if not mongo_service.get_subject_by_subject_id(old_pg.id):
                mongo_service.create_subject(
                    subject=mongo_schemas.SubjectDocCreate(
                        subject_id=old_pg.id,
                        name=old_pg.name,
                        root_subject_id=old_pg.root_subject_id,
                        synonyms=old_pg.synonyms or [],
                        description=old_pg.description,
                        categories=old_pg.categories or []
                    )
                )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

# ========== INFERENCE QUERIES ==========
@router.post("/inference/subject-to-diagram", response_model=Dict[str, Any])
def infer_diagram_from_subjects(
    subject_names: List[str],
    relationship_hint: Optional[str] = None
):
    """Infer diagrams from subject names (e.g., ['bee', 'flower'] -> foodChainsWebs diagrams)"""
    neo4j_service = Neo4jService()
    
    try:
        # Get inferred categories
        inferred_categories = neo4j_service.infer_categories_from_subjects(subject_names)
        
        # Find diagrams
        diagrams = neo4j_service.find_diagrams_by_subject_inference(
            subject_names, 
            relationship_hint=relationship_hint
        )
        
        return {
            "success": True,
            "subject_names": subject_names,
            "inferred_categories": inferred_categories,
            "diagrams": diagrams,
            "total_diagrams": len(diagrams)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

@router.post("/subjects/{subject_id}/link-categories")
def link_subject_to_categories(
    subject_id: int,
    category_names: List[str]
):
    """Link a Subject to Categories for inference"""
    neo4j_service = Neo4jService()
    
    try:
        success = neo4j_service.link_subject_to_categories(subject_id, category_names)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to link subject to categories")
        
        return {
            "success": True,
            "message": f"Subject {subject_id} linked to {len(category_names)} categories"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()

@router.post("/subjects/relationship")
def create_subject_relationship_endpoint(
    from_subject_id: int,
    to_subject_id: int,
    relationship_type: str,
    properties: Optional[Dict[str, Any]] = None
):
    """Create relationship between two Subjects (e.g., bee -[FEEDS_ON]-> flower)"""
    neo4j_service = Neo4jService()
    
    try:
        success = neo4j_service.create_subject_relationship(
            from_subject_id, 
            to_subject_id, 
            relationship_type, 
            properties
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create subject relationship")
        
        return {
            "success": True,
            "from_subject_id": from_subject_id,
            "to_subject_id": to_subject_id,
            "relationship_type": relationship_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        neo4j_service.close()