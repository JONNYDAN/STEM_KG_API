# app/services/neo4j_service.py
from app.database.neo4j_conn import get_neo4j_session
from app.schemas.neo4j_schemas import NodeCreate, RelationshipCreate, NodeSelector
from typing import List, Dict, Any, Optional
import re
from datetime import datetime

def _serialize_neo4j_dict(node_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Neo4j types (like neo4j.time.DateTime) to JSON-serializable types"""
    if not isinstance(node_dict, dict):
        return node_dict
    
    result = {}
    for key, value in node_dict.items():
        # Handle neo4j.time.DateTime
        if hasattr(value, 'iso_format'):  # neo4j.time.DateTime has iso_format method
            result[key] = value.iso_format()
        # Handle datetime objects
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        # Handle lists
        elif isinstance(value, list):
            result[key] = [_serialize_neo4j_dict(v) if isinstance(v, dict) else v for v in value]
        # Handle dicts
        elif isinstance(value, dict):
            result[key] = _serialize_neo4j_dict(value)
        else:
            result[key] = value
    
    return result

class Neo4jService:
    def __init__(self):
        self.session = get_neo4j_session()

    def _validate_identifier(self, value: str, field_name: str) -> None:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
            raise ValueError(f"Invalid {field_name}: {value}")

    def _format_labels(self, labels: List[str]) -> str:
        for label in labels:
            self._validate_identifier(label, "label")
        return ":".join(labels)

    def _selector_match(self, selector: NodeSelector, alias: str) -> str:
        self._validate_identifier(selector.label, "label")
        self._validate_identifier(selector.key, "key")
        return f"({alias}:{selector.label} {{{selector.key}: ${alias}_value}})"
    
    def create_node(self, node_data: NodeCreate) -> Dict[str, Any]:
        """Tạo node mới trong Neo4j"""
        if node_data.labels:
            labels = self._format_labels(node_data.labels)
            properties = dict(node_data.properties or {})

            # Merge legacy fields if provided
            if node_data.id is not None and "id" not in properties:
                properties["id"] = node_data.id
            if node_data.name is not None and "name" not in properties:
                properties["name"] = node_data.name
            if node_data.type is not None and "type" not in properties:
                properties["type"] = node_data.type
            if node_data.category is not None and "category" not in properties:
                properties["category"] = node_data.category

            query = f"""
            CREATE (n:{labels})
            SET n += $properties
            SET n.created_at = datetime()
            RETURN n
            """
            result = self.session.run(query, properties=properties)
        else:
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
        if rel_data.from_node and rel_data.to_node:
            self._validate_identifier(rel_data.relationship_type, "relationship_type")
            match_a = self._selector_match(rel_data.from_node, "a")
            match_b = self._selector_match(rel_data.to_node, "b")

            properties = dict(rel_data.properties or {})
            if rel_data.name is not None and "name" not in properties:
                properties["name"] = rel_data.name
            if rel_data.confidence is not None and "confidence" not in properties:
                properties["confidence"] = rel_data.confidence

            query = f"""
            MATCH {match_a}
            MATCH {match_b}
            CREATE (a)-[r:{rel_data.relationship_type}]->(b)
            SET r += $properties
            SET r.created_at = datetime()
            RETURN a, r, b
            """

            result = self.session.run(
                query,
                a_value=rel_data.from_node.value,
                b_value=rel_data.to_node.value,
                properties=properties
            )
        else:
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
    
    def search_diagrams_by_triple(
        self,
        subject: str,
        relationship: str,
        object: str,
        subject_label: Optional[str] = None,
        object_label: Optional[str] = None,
        relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Tìm diagrams phù hợp với bộ ba"""
        if subject_label and object_label:
            self._validate_identifier(subject_label, "subject_label")
            self._validate_identifier(object_label, "object_label")

            rel_type = relationship_type or "RELATES"
            self._validate_identifier(rel_type, "relationship_type")

            query = f"""
            MATCH (s:{subject_label})-[r:{rel_type}]->(o:{object_label})
            WHERE toLower(s.name) CONTAINS toLower($subject)
            AND toLower(o.name) CONTAINS toLower($object)
            AND (
                (exists(r.name) AND toLower(r.name) CONTAINS toLower($relationship))
                OR toLower(type(r)) CONTAINS toLower($relationship)
            )
            RETURN 
                s.id as subject_id, 
                s.name as subject_name,
                coalesce(r.name, type(r)) as relationship,
                o.id as object_id,
                o.name as object_name,
                s.category as category,
                r.confidence as confidence,
                s.properties['diagram_id'] as diagram_id
            ORDER BY r.confidence DESC
            LIMIT 10
            """
            result = self.session.run(
                query,
                subject=subject,
                relationship=relationship,
                object=object
            )
        else:
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
            result = self.session.run(
                query,
                subject=subject,
                relationship=relationship,
                object=object
            )

        return [
            {
                "subject_id": record["subject_id"],
                "subject_name": record["subject_name"],
                "relationship": record["relationship"],
                "object_id": record["object_id"],
                "object_name": record["object_name"],
                "category": record["category"],
                "confidence": record["confidence"],
                "diagram_id": record["diagram_id"]
            }
            for record in result
        ]
    
    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        query = "MATCH (n:STEM_NODE {id: $node_id}) RETURN n"
        result = self.session.run(query, node_id=node_id)
        record = result.single()
        return dict(record[0]) if record else None

    def get_node_by_key(self, label: str, key: str, value: Any) -> Optional[Dict[str, Any]]:
        self._validate_identifier(label, "label")
        self._validate_identifier(key, "key")
        query = f"MATCH (n:{label} {{{key}: $value}}) RETURN n"
        result = self.session.run(query, value=value)
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

    def update_node_by_key(self, label: str, key: str, value: Any, properties: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self._validate_identifier(label, "label")
        self._validate_identifier(key, "key")
        query = f"""
        MATCH (n:{label} {{{key}: $value}})
        SET n += $properties
        RETURN n
        """
        result = self.session.run(query, value=value, properties=properties)
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

    def delete_node_by_key(self, label: str, key: str, value: Any) -> bool:
        self._validate_identifier(label, "label")
        self._validate_identifier(key, "key")
        query = f"""
        MATCH (n:{label} {{{key}: $value}})
        DETACH DELETE n
        RETURN COUNT(n) as deleted_count
        """
        result = self.session.run(query, value=value)
        return result.single()["deleted_count"] > 0
    
    def get_all_nodes(self, limit: int = 100, label: Optional[str] = None) -> List[Dict[str, Any]]:
        if label:
            self._validate_identifier(label, "label")
            query = f"""
            MATCH (n:{label})
            RETURN n
            LIMIT $limit
            """
        else:
            query = """
            MATCH (n)
            RETURN n
            LIMIT $limit
            """
        result = self.session.run(query, limit=limit)
        return [dict(record["n"]) for record in result]

    # ========== ROOT SUBJECTS ==========
    def create_root_subject(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Ensure Root node exists
            root_check = self.session.run(
                "MERGE (root:Root {name: 'AI2D_Knowledge_Graph'}) RETURN root"
            ).single()
            
            query = """
            MERGE (rs:RootSubject {id: $id})
            SET rs.name = $name,
                rs.description = $description,
                rs.parent_id = $parent_id,
                rs.level = $level,
                rs.created_at = datetime()
            RETURN rs
            """
            result = self.session.run(query, **data)
            record = result.single()
            
            if not record:
                return None

            rs_node = _serialize_neo4j_dict(dict(record[0]))

            # Link to Root node
            root_link = """
            MATCH (root:Root {name: 'AI2D_Knowledge_Graph'})
            MATCH (rs:RootSubject {id: $id})
            MERGE (root)-[:HAS_ROOT_SUBJECT]->(rs)
            """
            self.session.run(root_link, id=data.get("id"))

            if data.get("parent_id") is not None:
                rel_query = """
                MATCH (parent:RootSubject {id: $parent_id})
                MATCH (child:RootSubject {id: $id})
                MERGE (parent)-[:HAS_CHILD_ROOT_SUBJECT]->(child)
                """
                self.session.run(rel_query, parent_id=data.get("parent_id"), id=data.get("id"))

            return rs_node
        except Exception as e:
            print(f"Neo4j create_root_subject error: {e}")
            return None

    def get_root_subject(self, root_subject_id: int) -> Optional[Dict[str, Any]]:
        query = "MATCH (rs:RootSubject {id: $id}) RETURN rs"
        result = self.session.run(query, id=root_subject_id)
        record = result.single()
        return dict(record["rs"]) if record else None

    def update_root_subject(self, root_subject_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (rs:RootSubject {id: $id})
        SET rs += $properties
        RETURN rs
        """
        result = self.session.run(query, id=root_subject_id, properties=update_data)
        record = result.single()

        if "parent_id" in update_data:
            rel_cleanup = """
            MATCH (rs:RootSubject {id: $id})
            OPTIONAL MATCH (p:RootSubject)-[r:HAS_CHILD_ROOT_SUBJECT]->(rs)
            DELETE r
            """
            self.session.run(rel_cleanup, id=root_subject_id)

            if update_data.get("parent_id") is not None:
                rel_query = """
                MATCH (parent:RootSubject {id: $parent_id})
                MATCH (child:RootSubject {id: $id})
                MERGE (parent)-[:HAS_CHILD_ROOT_SUBJECT]->(child)
                """
                self.session.run(rel_query, parent_id=update_data.get("parent_id"), id=root_subject_id)

        return dict(record["rs"]) if record else None

    def delete_root_subject(self, root_subject_id: int) -> bool:
        query = """
        MATCH (rs:RootSubject {id: $id})
        DETACH DELETE rs
        RETURN COUNT(rs) as deleted_count
        """
        result = self.session.run(query, id=root_subject_id)
        return result.single()["deleted_count"] > 0

    # ========== SUBJECTS ==========
    def create_subject(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Ensure Root node exists
            root_check = self.session.run(
                "MERGE (root:Root {name: 'AI2D_Knowledge_Graph'}) RETURN root"
            ).single()
            
            query = """
            MERGE (s:Subject {id: $id})
            SET s.name = $name,
                s.root_subject_id = $root_subject_id,
                s.synonyms = $synonyms,
                s.description = $description,
                s.created_at = datetime()
            RETURN s
            """
            result = self.session.run(query, **data)
            record = result.single()
            
            if not record:
                return None

            s_node = _serialize_neo4j_dict(dict(record[0]))

            # Link to RootSubject
            rel_query = """
            MATCH (rs:RootSubject {id: $root_subject_id})
            MATCH (s:Subject {id: $id})
            MERGE (rs)-[:HAS_SUBJECT]->(s)
            """
            self.session.run(rel_query, root_subject_id=data.get("root_subject_id"), id=data.get("id"))

            # Link to Categories if provided
            if data.get("categories"):
                for category_name in data.get("categories", []):
                    cat_link = """
                    MATCH (s:Subject {id: $id})
                    MATCH (c:Category {name: $category_name})
                    MERGE (s)-[:BELONGS_TO_CATEGORY]->(c)
                    """
                    self.session.run(cat_link, id=data.get("id"), category_name=category_name)

            return s_node
        except Exception as e:
            print(f"Neo4j create_subject error: {e}")
            return None

    def get_subject(self, subject_id: int) -> Optional[Dict[str, Any]]:
        query = "MATCH (s:Subject {id: $id}) RETURN s"
        result = self.session.run(query, id=subject_id)
        record = result.single()
        return dict(record["s"]) if record else None

    def update_subject(self, subject_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        query = """
        MATCH (s:Subject {id: $id})
        SET s += $properties
        RETURN s
        """
        result = self.session.run(query, id=subject_id, properties=update_data)
        record = result.single()

        if "root_subject_id" in update_data:
            rel_cleanup = """
            MATCH (s:Subject {id: $id})
            OPTIONAL MATCH (rs:RootSubject)-[r:HAS_SUBJECT]->(s)
            DELETE r
            """
            self.session.run(rel_cleanup, id=subject_id)

            if update_data.get("root_subject_id") is not None:
                rel_query = """
                MATCH (rs:RootSubject {id: $root_subject_id})
                MATCH (s:Subject {id: $id})
                MERGE (rs)-[:HAS_SUBJECT]->(s)
                """
                self.session.run(rel_query, root_subject_id=update_data.get("root_subject_id"), id=subject_id)

        return dict(record["s"]) if record else None

    def delete_subject(self, subject_id: int) -> bool:
        query = """
        MATCH (s:Subject {id: $id})
        DETACH DELETE s
        RETURN COUNT(s) as deleted_count
        """
        result = self.session.run(query, id=subject_id)
        return result.single()["deleted_count"] > 0

    def link_subject_to_categories(self, subject_id: int, category_names: List[str]) -> bool:
        """Link a Subject to one or more Categories for inference"""
        try:
            for category_name in category_names:
                query = """
                MATCH (s:Subject {id: $subject_id})
                MATCH (c:Category {name: $category_name})
                MERGE (s)-[:BELONGS_TO_CATEGORY]->(c)
                """
                self.session.run(query, subject_id=subject_id, category_name=category_name)
            return True
        except Exception:
            return False

    def create_subject_relationship(self, from_subject_id: int, to_subject_id: int, 
                                   relationship_type: str, properties: Optional[Dict[str, Any]] = None) -> bool:
        """Create relationship between two Subjects (e.g., bee -[FEEDS_ON]-> flower)"""
        try:
            self._validate_identifier(relationship_type, "relationship_type")
            props = properties or {}
            query = f"""
            MATCH (s1:Subject {{id: $from_id}})
            MATCH (s2:Subject {{id: $to_id}})
            MERGE (s1)-[r:{relationship_type}]->(s2)
            SET r += $properties
            RETURN r
            """
            self.session.run(query, from_id=from_subject_id, to_id=to_subject_id, properties=props)
            return True
        except Exception:
            return False

    def infer_categories_from_subjects(self, subject_names: List[str]) -> List[Dict[str, Any]]:
        """Infer categories based on Subject names (e.g., 'bee', 'flower' -> 'foodChainsWebs')"""
        query = """
        UNWIND $subject_names AS subject_name
        MATCH (s:Subject)
        WHERE toLower(s.name) CONTAINS toLower(subject_name) 
           OR any(syn IN s.synonyms WHERE toLower(syn) CONTAINS toLower(subject_name))
        MATCH (s)-[:BELONGS_TO_CATEGORY]->(c:Category)
        RETURN DISTINCT c.name as category_name, count(s) as subject_count
        ORDER BY subject_count DESC
        """
        result = self.session.run(query, subject_names=subject_names)
        return [dict(record) for record in result]

    def find_diagrams_by_subject_inference(self, subject_names: List[str], 
                                          relationship_hint: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find diagrams by inferring category from subjects (bee on flower -> foodChainsWebs diagrams)"""
        # First, infer categories
        inferred_categories = self.infer_categories_from_subjects(subject_names)
        
        if not inferred_categories:
            return []
        
        # Get diagrams from top inferred category
        top_category = inferred_categories[0]["category_name"]
        
        query = """
        MATCH (c:Category {name: $category_name})-[:CONTAINS]->(d:Diagram)
        OPTIONAL MATCH (d)-[:HAS_TEXT_LABEL]->(tl:TextLabel)
        WHERE any(subject_name IN $subject_names 
                  WHERE toLower(tl.value) CONTAINS toLower(subject_name) 
                     OR toLower(tl.replacement_text) CONTAINS toLower(subject_name))
        RETURN DISTINCT d.id as diagram_id, 
               d.category as category, 
               count(tl) as matching_labels,
               collect(DISTINCT tl.value) as matched_text
        ORDER BY matching_labels DESC
        LIMIT 10
        """
        result = self.session.run(query, category_name=top_category, subject_names=subject_names)
        
        return [{
            "diagram_id": record["diagram_id"],
            "category": record["category"],
            "inferred_category": top_category,
            "matching_labels": record["matching_labels"],
            "matched_text": record["matched_text"]
        } for record in result]
    
    def close(self):
        if self.session:
            self.session.close()