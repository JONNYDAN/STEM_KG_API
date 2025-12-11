from sqlalchemy import Column, Integer, String, Text, Boolean, JSON, DateTime, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship as orm_relationship 
from app.database.postgres_conn import Base

class RootCategory(Base):
    __tablename__ = "root_categories"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    categories = orm_relationship("Category", back_populates="root_category")

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    root_category_id = Column(String(50), ForeignKey("root_categories.id"))
    description = Column(Text)
    diagram_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    root_category = orm_relationship("RootCategory", back_populates="categories")
    diagrams = orm_relationship("Diagram", back_populates="category")

class Diagram(Base):
    __tablename__ = "diagrams"
    
    id = Column(String(50), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    image_path = Column(String(500))
    processed = Column(Boolean, default=False)
    diagram_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    category = orm_relationship("Category", back_populates="diagrams")

class RootSubject(Base):
    __tablename__ = "root_subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey("root_subjects.id"))
    level = Column(Integer, default=0)
    
    parent = orm_relationship("RootSubject", remote_side=[id], backref="children")
    subjects = orm_relationship("Subject", back_populates="root_subject")

class Subject(Base):
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    root_subject_id = Column(Integer, ForeignKey("root_subjects.id"))
    synonyms = Column(JSON)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    root_subject = orm_relationship("RootSubject", back_populates="subjects")

class Relationship(Base):
    __tablename__ = "relationships"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    inverse_relationship = Column(String(100))
    semantic_type = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SubjectRelationshipObject(Base):
    __tablename__ = "subject_relationship_object"
    
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"))
    relationship_id = Column(Integer, ForeignKey("relationships.id"))
    object_id = Column(Integer, ForeignKey("subjects.id"))
    diagram_id = Column(String(50), ForeignKey("diagrams.id"))
    confidence_score = Column(DECIMAL(3, 2))
    context = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    subject = orm_relationship("Subject", foreign_keys=[subject_id])
    relationship = orm_relationship("Relationship", foreign_keys=[relationship_id])
    object_rel = orm_relationship("Subject", foreign_keys=[object_id], overlaps="subject")  
    diagram = orm_relationship("Diagram")