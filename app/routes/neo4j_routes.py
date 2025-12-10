# app/routes/neo4j_routes.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from app.services.neo4j_service import Neo4jService
from app.schemas.neo4j_schemas import NodeCreate, RelationshipCreate

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
def get_all_nodes(limit: int = 100):
    """Lấy tất cả nodes"""
    service = Neo4jService()
    try:
        nodes = service.get_all_nodes(limit)
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

@router.get("/search/triple")
def search_by_triple(
    subject: str,
    relationship: str,
    object: str
) -> List[Dict[str, Any]]:
    """Tìm kiếm bằng bộ ba"""
    service = Neo4jService()
    try:
        results = service.search_diagrams_by_triple(subject, relationship, object)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close()