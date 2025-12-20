```
STEM_KG_API/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── postgres_models.py
│   │   ├── mongo_models.py
│   │   └── neo4j_models.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── postgres_schemas.py
│   │   ├── mongo_schemas.py
│   │   └── neo4j_schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── postgres_service.py
│   │   ├── mongo_service.py
│   │   ├── neo4j_service.py
│   │   └── integration_service.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── postgres_routes.py
│   │   ├── mongo_routes.py
│   │   ├── neo4j_routes.py
│   │   ├── integration_routes.py
│   │   └── search_routes.py
│   └── database/
│       ├── __init__.py
│       ├── postgres_conn.py
│       ├── mongo_conn.py
│       └── neo4j_conn.py
├── requirements.txt
├── .env.example
├── docker-compose.yml
└── README.md      
```

# Khởi động hệ thống
docker-compose up -d

# API sẽ có sẵn tại: http://localhost:8000

# Truy vấn bộ ba
curl "http://localhost:8000/api/integration/search/triple?subject=bee&relationship=on_top_of&object=flower"

# Tạo root category mới
curl -X POST "http://localhost:8000/api/postgres/root-categories/" \
  -H "Content-Type: application/json" \
  -d '{"id": "new_category", "name": "New Category", "description": "Test category"}'

# Tìm kiếm theo category
curl "http://localhost:8000/api/integration/search/category/foodChainsWebs"
