from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models import postgres_models as models
from app.schemas import postgres_schemas as schemas
from typing import List, Optional, Dict, Any

class PostgresService:
    def __init__(self, db: Session):
        self.db = db
    
    # ========== ROOT CATEGORIES ==========
    def create_root_category(self, category: schemas.RootCategoryCreate) -> models.RootCategory:
        db_category = models.RootCategory(**category.model_dump())
        self.db.add(db_category)
        self.db.commit()
        self.db.refresh(db_category)
        return db_category
    
    def get_root_category(self, category_id: str) -> Optional[models.RootCategory]:
        return self.db.query(models.RootCategory).filter(models.RootCategory.id == category_id).first()
    
    def get_all_root_categories(self) -> List[models.RootCategory]:
        return self.db.query(models.RootCategory).all()
    
    def update_root_category(self, category_id: str, category_update: schemas.RootCategoryUpdate) -> Optional[models.RootCategory]:
        db_category = self.get_root_category(category_id)
        if db_category:
            update_data = category_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
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
    
    # ========== CATEGORIES ==========
    def create_category(self, category: schemas.CategoryCreate) -> models.Category:
        db_category = models.Category(**category.model_dump())
        self.db.add(db_category)
        self.db.commit()
        self.db.refresh(db_category)
        return db_category
    
    def get_category(self, category_id: int) -> Optional[models.Category]:
        return self.db.query(models.Category).filter(models.Category.id == category_id).first()
    
    def get_categories_by_root(self, root_category_id: str) -> List[models.Category]:
        return self.db.query(models.Category).filter(models.Category.root_category_id == root_category_id).all()
    
    def get_all_categories(self, skip: int = 0, limit: int = 100) -> List[models.Category]:
        return self.db.query(models.Category).offset(skip).limit(limit).all()
    
    def update_category(self, category_id: int, category_update: schemas.CategoryUpdate) -> Optional[models.Category]:
        db_category = self.get_category(category_id)
        if db_category:
            update_data = category_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
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
    
    # ========== DIAGRAMS ==========
    def create_diagram(self, diagram: schemas.DiagramCreate) -> models.Diagram:
        db_diagram = models.Diagram(**diagram.model_dump())
        self.db.add(db_diagram)
        self.db.commit()
        self.db.refresh(db_diagram)
        return db_diagram
    
    def get_diagram(self, diagram_id: str) -> Optional[models.Diagram]:
        return self.db.query(models.Diagram).filter(models.Diagram.id == diagram_id).first()
    
    def get_diagrams_by_category(self, category_id: int, skip: int = 0, limit: int = 100) -> List[models.Diagram]:
        return self.db.query(models.Diagram)\
            .filter(models.Diagram.category_id == category_id)\
            .offset(skip).limit(limit).all()
    
    def get_all_diagrams(self, skip: int = 0, limit: int = 100) -> List[models.Diagram]:
        return self.db.query(models.Diagram).offset(skip).limit(limit).all()
    
    def update_diagram(self, diagram_id: str, diagram_update: schemas.DiagramUpdate) -> Optional[models.Diagram]:
        db_diagram = self.get_diagram(diagram_id)
        if db_diagram:
            update_data = diagram_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_diagram, key, value)
            self.db.commit()
            self.db.refresh(db_diagram)
        return db_diagram
    
    def delete_diagram(self, diagram_id: str) -> bool:
        db_diagram = self.get_diagram(diagram_id)
        if db_diagram:
            self.db.delete(db_diagram)
            self.db.commit()
            return True
        return False
    
    # ========== ROOT SUBJECTS ==========
    def create_root_subject(self, root_subject: schemas.RootSubjectCreate) -> models.RootSubject:
        """Create or update root subject. If id provided and exists, update instead of insert."""
        # Check if id is provided and already exists
        if hasattr(root_subject, 'id') and root_subject.id:
            existing = self.get_root_subject(root_subject.id)
            if existing:
                # Update the existing record
                return self.update_root_subject(root_subject.id, schemas.RootSubjectUpdate(**root_subject.model_dump(exclude={'id'})))
        
        # Create new record
        db_root_subject = models.RootSubject(**root_subject.model_dump(exclude={'id'} if not root_subject.id else set()))
        self.db.add(db_root_subject)
        try:
            self.db.commit()
            self.db.refresh(db_root_subject)
        except Exception as e:
            self.db.rollback()
            # If duplicate key error, try to fetch and return existing
            if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                # Try to extract id from error or from request
                if hasattr(root_subject, 'id') and root_subject.id:
                    existing = self.get_root_subject(root_subject.id)
                    if existing:
                        return existing
            raise
        return db_root_subject
    
    def get_root_subject(self, root_subject_id: int) -> Optional[models.RootSubject]:
        return self.db.query(models.RootSubject).filter(models.RootSubject.id == root_subject_id).first()
    
    def get_all_root_subjects(self, skip: int = 0, limit: int = 100) -> List[models.RootSubject]:
        return self.db.query(models.RootSubject).offset(skip).limit(limit).all()
    
    def get_root_subjects_by_level(self, level: int) -> List[models.RootSubject]:
        return self.db.query(models.RootSubject).filter(models.RootSubject.level == level).all()
    
    def update_root_subject(self, root_subject_id: int, root_subject_update: schemas.RootSubjectUpdate) -> Optional[models.RootSubject]:
        db_root_subject = self.get_root_subject(root_subject_id)
        if db_root_subject:
            update_data = root_subject_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_root_subject, key, value)
            self.db.commit()
            self.db.refresh(db_root_subject)
        return db_root_subject
    
    def delete_root_subject(self, root_subject_id: int) -> bool:
        try:
            # First delete all subjects related to this root_subject
            subjects = self.get_subjects_by_root(root_subject_id, skip=0, limit=10000)
            for subject in subjects:
                self.delete_subject(subject.id)
            
            # Then delete the root_subject itself
            db_root_subject = self.db.query(models.RootSubject).filter(
                models.RootSubject.id == root_subject_id
            ).first()
            
            if db_root_subject:
                self.db.delete(db_root_subject)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            raise
    
    # ========== SUBJECTS ==========
    def create_subject(self, subject: schemas.SubjectCreate) -> models.Subject:
        """Create or update subject. If id provided and exists, update instead of insert."""
        # Check if id is provided and already exists
        if hasattr(subject, 'id') and subject.id:
            existing = self.get_subject(subject.id)
            if existing:
                # Update the existing record
                return self.update_subject(subject.id, schemas.SubjectUpdate(**subject.model_dump(exclude={'id'})))
        
        # Create new record
        db_subject = models.Subject(**subject.model_dump(exclude={'id'} if not subject.id else set()))
        self.db.add(db_subject)
        try:
            self.db.commit()
            self.db.refresh(db_subject)
        except Exception as e:
            self.db.rollback()
            # If duplicate key error, try to fetch and return existing
            if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
                # Try to extract id from error or from request
                if hasattr(subject, 'id') and subject.id:
                    existing = self.get_subject(subject.id)
                    if existing:
                        return existing
            raise
        return db_subject
    
    def get_subject(self, subject_id: int) -> Optional[models.Subject]:
        return self.db.query(models.Subject).filter(models.Subject.id == subject_id).first()
    
    def get_subjects_by_root(self, root_subject_id: int, skip: int = 0, limit: int = 100) -> List[models.Subject]:
        return self.db.query(models.Subject)\
            .filter(models.Subject.root_subject_id == root_subject_id)\
            .offset(skip).limit(limit).all()
    
    def get_all_subjects(self, skip: int = 0, limit: int = 100) -> List[models.Subject]:
        return self.db.query(models.Subject).offset(skip).limit(limit).all()
    
    def search_subjects(self, name: Optional[str] = None, root_subject_id: Optional[int] = None) -> List[models.Subject]:
        query = self.db.query(models.Subject)
        if name:
            query = query.filter(models.Subject.name.ilike(f"%{name}%"))
        if root_subject_id:
            query = query.filter(models.Subject.root_subject_id == root_subject_id)
        return query.all()
    
    def update_subject(self, subject_id: int, subject_update: schemas.SubjectUpdate) -> Optional[models.Subject]:
        db_subject = self.get_subject(subject_id)
        if db_subject:
            update_data = subject_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_subject, key, value)
            self.db.commit()
            self.db.refresh(db_subject)
        return db_subject
    
    def delete_subject(self, subject_id: int) -> bool:
        db_subject = self.get_subject(subject_id)
        if db_subject:
            self.db.delete(db_subject)
            self.db.commit()
            return True
        return False
    
    # ========== RELATIONSHIPS ==========
    def create_relationship(self, relationship: schemas.RelationshipCreate) -> models.Relationship:
        db_relationship = models.Relationship(**relationship.model_dump())
        self.db.add(db_relationship)
        self.db.commit()
        self.db.refresh(db_relationship)
        return db_relationship
    
    def get_relationship(self, relationship_id: int) -> Optional[models.Relationship]:
        return self.db.query(models.Relationship).filter(models.Relationship.id == relationship_id).first()
    
    def get_relationship_by_name(self, name: str) -> Optional[models.Relationship]:
        return self.db.query(models.Relationship).filter(models.Relationship.name == name).first()
    
    def get_all_relationships(self, skip: int = 0, limit: int = 100) -> List[models.Relationship]:
        return self.db.query(models.Relationship).offset(skip).limit(limit).all()
    
    def get_relationships_by_type(self, semantic_type: str) -> List[models.Relationship]:
        return self.db.query(models.Relationship).filter(models.Relationship.semantic_type == semantic_type).all()
    
    def update_relationship(self, relationship_id: int, relationship_update: schemas.RelationshipUpdate) -> Optional[models.Relationship]:
        db_relationship = self.get_relationship(relationship_id)
        if db_relationship:
            update_data = relationship_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_relationship, key, value)
            self.db.commit()
            self.db.refresh(db_relationship)
        return db_relationship
    
    def delete_relationship(self, relationship_id: int) -> bool:
        db_relationship = self.get_relationship(relationship_id)
        if db_relationship:
            self.db.delete(db_relationship)
            self.db.commit()
            return True
        return False
    
    # ========== SUBJECT-RELATIONSHIP-OBJECT (SRO) ==========
    def create_sro(self, sro: schemas.SROCreate) -> models.SubjectRelationshipObject:
        db_sro = models.SubjectRelationshipObject(**sro.model_dump())
        self.db.add(db_sro)
        self.db.commit()
        self.db.refresh(db_sro)
        return db_sro
    
    def get_sro(self, sro_id: int) -> Optional[models.SubjectRelationshipObject]:
        return self.db.query(models.SubjectRelationshipObject)\
            .filter(models.SubjectRelationshipObject.id == sro_id).first()
    
    def get_sro_by_triple(self, subject_id: int, relationship_id: int, object_id: int) -> Optional[models.SubjectRelationshipObject]:
        return self.db.query(models.SubjectRelationshipObject)\
            .filter(
                models.SubjectRelationshipObject.subject_id == subject_id,
                models.SubjectRelationshipObject.relationship_id == relationship_id,
                models.SubjectRelationshipObject.object_id == object_id
            ).first()
    
    def get_all_sros(self, skip: int = 0, limit: int = 100) -> List[models.SubjectRelationshipObject]:
        return self.db.query(models.SubjectRelationshipObject)\
            .offset(skip).limit(limit).all()
    
    def get_sros_by_diagram(self, diagram_id: str) -> List[models.SubjectRelationshipObject]:
        return self.db.query(models.SubjectRelationshipObject)\
            .filter(models.SubjectRelationshipObject.diagram_id == diagram_id).all()
    
    def get_sros_by_subject(self, subject_id: int) -> List[models.SubjectRelationshipObject]:
        return self.db.query(models.SubjectRelationshipObject)\
            .filter(models.SubjectRelationshipObject.subject_id == subject_id).all()
    
    def get_sros_by_object(self, object_id: int) -> List[models.SubjectRelationshipObject]:
        return self.db.query(models.SubjectRelationshipObject)\
            .filter(models.SubjectRelationshipObject.object_id == object_id).all()
    
    def search_sros(self, 
                   subject_name: Optional[str] = None,
                   relationship_name: Optional[str] = None,
                   object_name: Optional[str] = None,
                   diagram_id: Optional[str] = None,
                   min_confidence: Optional[float] = None) -> List[Dict[str, Any]]:
        query = self.db.query(
            models.SubjectRelationshipObject,
            models.Subject.name.label('subject_name'),
            models.Relationship.name.label('relationship_name'),
            models.Subject_1.name.label('object_name')
        )\
        .join(models.Subject, models.SubjectRelationshipObject.subject_id == models.Subject.id)\
        .join(models.Relationship, models.SubjectRelationshipObject.relationship_id == models.Relationship.id)\
        .join(models.Subject, models.SubjectRelationshipObject.object_id == models.Subject.id)\
        
        if subject_name:
            query = query.filter(models.Subject.name.ilike(f"%{subject_name}%"))
        if relationship_name:
            query = query.filter(models.Relationship.name.ilike(f"%{relationship_name}%"))
        if object_name:
            query = query.filter(models.Subject_1.name.ilike(f"%{object_name}%"))
        if diagram_id:
            query = query.filter(models.SubjectRelationshipObject.diagram_id == diagram_id)
        if min_confidence:
            query = query.filter(models.SubjectRelationshipObject.confidence_score >= min_confidence)
        
        results = query.all()
        
        return [{
            'id': result.SubjectRelationshipObject.id,
            'subject_id': result.SubjectRelationshipObject.subject_id,
            'subject_name': result.subject_name,
            'relationship_id': result.SubjectRelationshipObject.relationship_id,
            'relationship_name': result.relationship_name,
            'object_id': result.SubjectRelationshipObject.object_id,
            'object_name': result.object_name,
            'diagram_id': result.SubjectRelationshipObject.diagram_id,
            'confidence_score': float(result.SubjectRelationshipObject.confidence_score) if result.SubjectRelationshipObject.confidence_score else 0.0,
            'context': result.SubjectRelationshipObject.context,
            'created_at': result.SubjectRelationshipObject.created_at
        } for result in results]
    
    def update_sro(self, sro_id: int, sro_update: schemas.SROUpdate) -> Optional[models.SubjectRelationshipObject]:
        db_sro = self.get_sro(sro_id)
        if db_sro:
            update_data = sro_update.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_sro, key, value)
            self.db.commit()
            self.db.refresh(db_sro)
        return db_sro
    
    def delete_sro(self, sro_id: int) -> bool:
        db_sro = self.get_sro(sro_id)
        if db_sro:
            self.db.delete(db_sro)
            self.db.commit()
            return True
        return False
    
    # ========== SEARCH AND UTILITY METHODS ==========
    def search_categories_by_triple(self, subject: str, relationship: str, object: str) -> List[Dict[str, Any]]:
        """Tìm categories phù hợp với bộ ba (subject-relationship-object)"""
        # Sử dụng raw SQL để search phức tạp
        from sqlalchemy import text
        
        query = text("""
        SELECT 
            c.id as category_id,
            c.name as category_name,
            rc.name as root_category,
            COUNT(sro.id) as match_count,
            AVG(sro.confidence_score) as avg_confidence,
            (COUNT(sro.id) * 0.5 + COALESCE(AVG(sro.confidence_score), 0) * 0.5) as relevance_score
        FROM categories c
        LEFT JOIN root_categories rc ON c.root_category_id = rc.id
        LEFT JOIN diagrams d ON c.id = d.category_id
        LEFT JOIN subject_relationship_object sro ON d.id = sro.diagram_id
        LEFT JOIN subjects s1 ON sro.subject_id = s1.id
        LEFT JOIN relationships r ON sro.relationship_id = r.id
        LEFT JOIN subjects s2 ON sro.object_id = s2.id
        WHERE (s1.name ILIKE :subject_pattern OR :subject = ANY(s1.synonyms))
        AND (r.name ILIKE :rel_pattern OR r.name IN (
            SELECT name FROM relationships WHERE inverse_relationship ILIKE :rel_pattern
        ))
        AND (s2.name ILIKE :object_pattern OR :object = ANY(s2.synonyms))
        GROUP BY c.id, c.name, rc.name
        ORDER BY relevance_score DESC
        """)
        
        result = self.db.execute(query, {
            'subject_pattern': f"%{subject}%",
            'subject': subject,
            'rel_pattern': f"%{relationship}%",
            'object_pattern': f"%{object}%",
            'object': object
        }).fetchall()
        
        return [{
            "category_id": row[0],
            "category_name": row[1],
            "root_category": row[2],
            "match_count": row[3],
            "avg_confidence": float(row[4]) if row[4] else 0,
            "relevance_score": float(row[5]) if row[5] else 0
        } for row in result]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Lấy thống kê tổng quan"""
        total_categories = self.db.query(func.count(models.Category.id)).scalar() or 0
        total_diagrams = self.db.query(func.count(models.Diagram.id)).scalar() or 0
        total_subjects = self.db.query(func.count(models.Subject.id)).scalar() or 0
        total_sros = self.db.query(func.count(models.SubjectRelationshipObject.id)).scalar() or 0
        total_relationships = self.db.query(func.count(models.Relationship.id)).scalar() or 0
        
        return {
            "total_categories": total_categories,
            "total_diagrams": total_diagrams,
            "total_subjects": total_subjects,
            "total_relationships": total_relationships,
            "total_sros": total_sros
        }