from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models import postgres_models as models
from app.schemas import postgres_schemas as schemas
from typing import List, Optional, Dict, Any

class PostgresService:
    def __init__(self, db: Session):
        self.db = db
    
    # CRUD for RootCategory
    def create_root_category(self, category: schemas.RootCategoryCreate) -> models.RootCategory:
        db_category = models.RootCategory(**category.dict())
        self.db.add(db_category)
        self.db.commit()
        self.db.refresh(db_category)
        return db_category
    
    def get_root_category(self, category_id: str) -> Optional[models.RootCategory]:
        return self.db.query(models.RootCategory).filter(models.RootCategory.id == category_id).first()
    
    def get_all_root_categories(self) -> List[models.RootCategory]:
        return self.db.query(models.RootCategory).all()
    
    def update_root_category(self, category_id: str, category: schemas.RootCategoryCreate) -> Optional[models.RootCategory]:
        db_category = self.get_root_category(category_id)
        if db_category:
            for key, value in category.dict().items():
                setattr(db_category, key, value)
            self.db.commit()
            self.db.refresh(db_category)
        return db_category
    
    def delete_root_category(self, category_id: str) -> bool:
        db_category = self.get_root_category(category_id)
        if db_category:
            self.db.delete(db_category)
            self.db.commit()
            return True
        return False
    
    # CRUD for Category
    def create_category(self, category: schemas.CategoryCreate) -> models.Category:
        db_category = models.Category(**category.dict())
        self.db.add(db_category)
        self.db.commit()
        self.db.refresh(db_category)
        return db_category
    
    def get_category(self, category_id: int) -> Optional[models.Category]:
        return self.db.query(models.Category).filter(models.Category.id == category_id).first()
    
    def get_categories_by_root(self, root_category_id: str) -> List[models.Category]:
        return self.db.query(models.Category).filter(models.Category.root_category_id == root_category_id).all()
    
    def update_category(self, category_id: int, category: schemas.CategoryCreate) -> Optional[models.Category]:
        db_category = self.get_category(category_id)
        if db_category:
            for key, value in category.dict().items():
                setattr(db_category, key, value)
            self.db.commit()
            self.db.refresh(db_category)
        return db_category
    
    def delete_category(self, category_id: int) -> bool:
        db_category = self.get_category(category_id)
        if db_category:
            self.db.delete(db_category)
            self.db.commit()
            return True
        return False
    
    # Search categories by triple
    def search_categories_by_triple(self, subject: str, relationship: str, object: str) -> List[Dict[str, Any]]:
        """Tìm categories phù hợp với bộ ba (subject-relationship-object)"""
        query = """
        SELECT 
            c.id as category_id,
            c.name as category_name,
            rc.name as root_category,
            COUNT(sro.id) as match_count,
            AVG(sro.confidence_score) as avg_confidence,
            (COUNT(sro.id) * 0.5 + COALESCE(AVG(sro.confidence_score), 0) * 0.5) as relevance_score
        FROM categories c
        LEFT JOIN root_categories rc ON c.root_category_id = rc.id
        LEFT JOIN subject_relationship_object sro ON c.id = (
            SELECT category_id FROM diagrams WHERE id = sro.diagram_id
        )
        WHERE sro.id IN (
            SELECT sro.id FROM subject_relationship_object sro
            JOIN subjects s1 ON sro.subject_id = s1.id
            JOIN relationships r ON sro.relationship_id = r.id
            JOIN subjects s2 ON sro.object_id = s2.id
            WHERE (s1.name ILIKE %s OR %s = ANY(s1.synonyms))
            AND (r.name ILIKE %s OR r.name IN (
                SELECT name FROM relationships 
                WHERE inverse_relationship ILIKE %s
            ))
            AND (s2.name ILIKE %s OR %s = ANY(s2.synonyms))
        )
        GROUP BY c.id, c.name, rc.name
        ORDER BY relevance_score DESC
        """
        
        result = self.db.execute(query, (
            f"%{subject}%", subject,
            f"%{relationship}%", f"%{relationship}%",
            f"%{object}%", object
        )).fetchall()
        
        return [{
            "category_id": row[0],
            "category_name": row[1],
            "root_category": row[2],
            "match_count": row[3],
            "avg_confidence": float(row[4]) if row[4] else 0,
            "relevance_score": float(row[5]) if row[5] else 0
        } for row in result]
    
    # CRUD for other tables (Subject, Relationship, SRO, etc.)
    def create_subject(self, subject: schemas.SubjectCreate) -> models.Subject:
        db_subject = models.Subject(**subject.dict())
        self.db.add(db_subject)
        self.db.commit()
        self.db.refresh(db_subject)
        return db_subject
    
    def create_relationship(self, relationship: schemas.RelationshipCreate) -> models.Relationship:
        db_relationship = models.Relationship(**relationship.dict())
        self.db.add(db_relationship)
        self.db.commit()
        self.db.refresh(db_relationship)
        return db_relationship
    
    def create_sro(self, sro: schemas.SROCreate) -> models.SubjectRelationshipObject:
        db_sro = models.SubjectRelationshipObject(**sro.dict())
        self.db.add(db_sro)
        self.db.commit()
        self.db.refresh(db_sro)
        return db_sro