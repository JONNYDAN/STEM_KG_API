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

# Auto-test định lượng (Precision/Recall/F1/MAP)

- Chuẩn bị file qrels (ground truth), có thể tham khảo: `scripts/qrels_example.json`
- Chạy online (tool tự gọi API để lấy ranked diagrams):

```bash
python scripts/auto_test_retrieval_metrics.py \
  --qrels scripts/qrels_example.json \
  --base-url http://localhost:8000 \
  --analysis-mode gemini \
  --top-k 5 \
  --output metrics_report.json
```

- Chạy offline (đánh giá từ file predictions có sẵn, ví dụ smoke test report):

```bash
python scripts/auto_test_retrieval_metrics.py \
  --qrels scripts/qrels_example.json \
  --predictions-file smoke_test_report.json \
  --top-k 5 \
  --output metrics_report.json
```

- Định dạng tối thiểu của qrels:

```json
[
  {
    "id": 1,
    "query": "your query",
    "relevant_diagram_ids": ["diagram_a.png", "diagram_b.png"]
  }
]
```

- Định dạng tối thiểu của predictions (offline):

```json
[
  {
    "id": 1,
    "predicted_diagram_ids": ["diagram_x.png", "diagram_a.png", "diagram_b.png"]
  }
]
```

- Report xuất ra gồm:
  - `macro_precision@K`, `macro_recall@K`, `macro_f1@K`
  - `map@K` (Mean Average Precision at K)
  - bảng `per_query` cho từng truy vấn

# Benchmark lớn (100-1000 lượt) + XLSX + biểu đồ

Script: `scripts/benchmark_multimodal_experiment.py`

Tính năng:
- Chạy benchmark số lượng lớn (ví dụ 100-1000 truy vấn)
- Test đủ 3 mode đầu vào: `text`, `image`, `both`
- Đo thời gian theo 2 giai đoạn:
  - `model_analysis_ms`
  - `kg_query_ms`
- Đo tổng thời gian truy vấn (`client_total_ms`, `server_total_ms`)
- Tính các chỉ số `Precision@K`, `Recall@K`, `F1@K`, `MAP@K`
- Xuất báo cáo `.json` và `.xlsx` (kèm chart + kết luận tự động)

Ví dụ chạy 120 lượt:

```bash
python scripts/benchmark_multimodal_experiment.py \
  --base-url http://localhost:8000 \
  --runs 120 \
  --top-k 5 \
  --analysis-mode gemini \
  --input-modes text,image,both \
  --test-images-dir ../test_images \
  --output-json benchmark_experiment_report.json \
  --output-xlsx benchmark_experiment_report.xlsx
```

Ví dụ chạy 1000 lượt:

```bash
python scripts/benchmark_multimodal_experiment.py \
  --base-url http://localhost:8000 \
  --runs 1000 \
  --top-k 5 \
  --analysis-mode gemini \
  --input-modes text,image,both \
  --test-images-dir ../test_images \
  --output-json benchmark_1000.json \
  --output-xlsx benchmark_1000.xlsx
```

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
