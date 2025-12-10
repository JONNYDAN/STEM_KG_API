from pymongo import MongoClient
from app.config import config

class MongoDB:
    client = None
    db = None
    
    @classmethod
    def connect(cls):
        if config.MONGO_USER and config.MONGO_PASSWORD:
            connection_string = f"mongodb://{config.MONGO_USER}:{config.MONGO_PASSWORD}@{config.MONGO_HOST}:{config.MONGO_PORT}"
        else:
            connection_string = f"mongodb://{config.MONGO_HOST}:{config.MONGO_PORT}"
        
        cls.client = MongoClient(connection_string)
        cls.db = cls.client[config.MONGO_DB]
    
    @classmethod
    def get_db(cls):
        if cls.db is None:
            cls.connect()
        return cls.db
    
    @classmethod
    def close(cls):
        if cls.client:
            cls.client.close()

def get_mongo_db():
    return MongoDB.get_db()