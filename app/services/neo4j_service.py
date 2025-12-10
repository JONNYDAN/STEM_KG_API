# app/services/neo4j_service.py
from app.database.neo4j_conn import get_neo4j_session
from app.schemas.neo4j_schemas import NodeCreate, RelationshipCreate
from typing import List, Dict, Any, Optional

class Neo4jService:
    def __init__(self):
        self.session = get_neo4j_session()
    
    def create_node(self, node_data: NodeCreate) -> Dict[str, Any]:
        """Tạo node mới trong Neo4j"""
        query = """
        CREATE (n:STEM_NODE {
            id: $id,
            name: $name,
            type: $type,
            category: $category,
            properties: $properties,
            created_at: datetime()
        })
        RETURN n
        """
        
        result = self.session.run(query, **node_data.model_dump())
        node = result.single()[0]
        return dict(node)
    
    def create_relationship(self, rel_data: RelationshipCreate) -> Dict[str, Any]:
        """Tạo relationship giữa các node"""
        query = """
        MATCH (a:STEM_NODE {id: $from_node_id})
        MATCH (b:STEM_NODE {id: $to_node_id})
        CREATE (a)-[r:RELATES {
            type: $relationship_type,
            name: $name,
            confidence: $confidence,
            properties: $properties,
            created_at: datetime()
        }]->(b)
        RETURN a, r, b
        """
        
        result = self.session.run(query, **rel_data.model_dump())
        record = result.single()
        return {
            "from_node": dict(record[0]),
            "relationship": dict(record[1]),
            "to_node": dict(record[2])
        }
    
    def search_diagrams_by_triple(self, subject: str, relationship: str, object: str) -> List[Dict[str, Any]]:
        """Tìm diagrams phù hợp với bộ ba"""
        query = """
        MATCH (s:STEM_NODE)-[r:RELATES]->(o:STEM_NODE)
        WHERE toLower(s.name) CONTAINS toLower($subject)
        AND toLower(r.name) CONTAINS toLower($relationship)
        AND toLower(o.name) CONTAINS toLower($object)
        RETURN 
            s.id as subject_id, 
            s.name as subject_name,
            r.name as relationship,
            o.id as object_id,
            o.name as object_name,
            s.category as category,
            r.confidence as confidence,
            s.properties['diagram_id'] as diagram_id
        ORDER BY r.confidence DESC
        LIMIT 10
        """
        
        result = self.session.run(query, 
                                 subject=subject, 
                                 relationship=relationship, 
                                 object=object)
        
        return [{
            "subject_id": record["subject_id"],
            "subject_name": record["subject_name"],
            "relationship": record["relationship"],
            "object_id": record["object_id"],
            "object_name": record["object_name"],
            "category": record["category"],
            "confidence": record["confidence"],
            "diagram_id": record["diagram_id"]
        } for record in result]
    
    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        query = "MATCH (n:STEM_NODE {id: $node_id}) RETURN n"
        result = self.session.run(query, node_id=node_id)
        record = result.single()
        return dict(record[0]) if record else None
    
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (n:STEM_NODE {id: $node_id})
        SET n += $properties
        RETURN n
        """
        result = self.session.run(query, node_id=node_id, properties=properties)
        record = result.single()
        return dict(record[0]) if record else None
    
    def delete_node(self, node_id: str) -> bool:
        query = """
        MATCH (n:STEM_NODE {id: $node_id})
        DETACH DELETE n
        RETURN COUNT(n) as deleted_count
        """
        result = self.session.run(query, node_id=node_id)
        return result.single()["deleted_count"] > 0
    
    def get_all_nodes(self, limit: int = 100) -> List[Dict[str, Any]]:
        query = """
        MATCH (n:STEM_NODE)
        RETURN n
        LIMIT $limit
        """
        result = self.session.run(query, limit=limit)
        return [dict(record["n"]) for record in result]
    
    def close(self):
        if self.session:
            self.session.close()