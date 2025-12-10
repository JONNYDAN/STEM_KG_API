from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integration", tags=["Integration"])

@router.get("/search/triple")
def search_by_triple(
    subject: str = Query(..., description="Subject of the triple"),
    relationship: str = Query(..., description="Relationship of the triple"),
    object: str = Query(..., description="Object of the triple")
) -> Dict[str, Any]:
    """Tìm kiếm tích hợp từ cả 3 cơ sở dữ liệu dựa trên bộ ba"""
    service = IntegrationService()
    try:
        results = service.process_triple_query(subject, relationship, object)
        return {
            "success": True,
            "query": {"subject": subject, "relationship": relationship, "object": object},
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close_connections()

@router.get("/search/category/{category_name}")
def search_by_category(category_name: str) -> Dict[str, Any]:
    """Tìm kiếm tất cả thông tin theo category"""
    service = IntegrationService()
    try:
        results = service.search_by_category(category_name)
        return {
            "success": True,
            "category": category_name,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close_connections()

@router.post("/link/meta")
def link_meta_data(
    diagram_id: str,
    neo4j_node_id: str,
    postgres_id: int,
    mongo_doc_id: str
) -> Dict[str, Any]:
    """Liên kết metadata giữa các cơ sở dữ liệu"""
    service = IntegrationService()
    try:
        # Logic liên kết metadata giữa các DB
        # Có thể lưu vào bảng link_meta trong PostgreSQL
        return {
            "success": True,
            "message": "Metadata linked successfully",
            "links": {
                "diagram_id": diagram_id,
                "neo4j_node": neo4j_node_id,
                "postgres_record": postgres_id,
                "mongo_document": mongo_doc_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        service.close_connections()