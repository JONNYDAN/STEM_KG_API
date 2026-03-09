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

# (Tùy chọn) Bật trigger sinh mã tự động trong PostgreSQL
# Chạy sau khi các bảng đã được tạo
# psql -h <host> -U <user> -d <db> -f database/postgres_triggers.sql

# API sẽ có sẵn tại: http://localhost:8000

# Smoke test 10 input mẫu STEM (pha text hoặc multimodal)
python scripts/smoke_test_stem_queries.py --base-url http://localhost:8000

# Nếu muốn ép chạy multimodal (đính kèm cùng một ảnh cho tất cả mẫu)
python scripts/smoke_test_stem_queries.py --base-url http://localhost:8000 --image-path app/images/uploads/sample.jpg

# Truy vấn bộ ba
curl "http://localhost:8000/api/integration/search/triple?subject=bee&relationship=on_top_of&object=flower"

# Tạo root category mới
curl -X POST "http://localhost:8000/api/postgres/root-categories/" \
  -H "Content-Type: application/json" \
  -d '{"id": "new_category", "name": "New Category", "description": "Test category"}'

# Tìm kiếm theo category
curl "http://localhost:8000/api/integration/search/category/foodChainsWebs"

# Diagram upload & sync (Entity Management)

- Upload endpoint: `POST /api/entities/diagrams/upload` (multipart/form-data)
- Required fields: `root_category_id`, `category_name`, `image`
- Optional fields: `category_id`, `diagram_id`, `processed`
- Image files are stored in API folder `app/images` and served via `/images/{file_name}`
- On upload, diagram is upserted in PostgreSQL and synchronized to MongoDB
- Neo4j behavior for Diagram: only `MATCH (d:Diagram {id: ...}) SET ...` (no new node creation)

Example:

```bash
curl -X POST "http://localhost:8000/api/entities/diagrams/upload" \
  -F "root_category_id=Earth_Geological_Sciences" \
  -F "category_name=partsOfTheEarth" \
  -F "diagram_id=1701.png" \
  -F "image=@/path/to/1701.png"
```
