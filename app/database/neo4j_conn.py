from neo4j import GraphDatabase
from app.config import config

class Neo4jConnection:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Neo4jConnection, cls).__new__(cls)
            cls._instance.driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USER, config.NEO4J_PASSWORD)
            )
        return cls._instance
    
    def get_session(self):
        return self.driver.session()
    
    def close(self):
        if self.driver:
            self.driver.close()

def get_neo4j_session():
    connection = Neo4jConnection()
    return connection.get_session()