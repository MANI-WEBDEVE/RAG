# RAG (Retrival Augmented Generation)

I`m solve the problem of abc company.

problem 100 plus book on physical registry but engineer and worker are not sufficient time to read the book and search the book in registry.

so i thought why not to create RAG system.

but not simple this is not easu beacuse every document not digital or scan its physical book.


Our approch why not scan each book and convert in to PDF and literaly this solution work.


complete books scanning process.

Folder structure our RAG pipline.   

```
abc-library-rag/
│
├── data/
│   ├── raw/              ← Aapka 1GB data YAHAN aayega (untouched)
│   ├── processed/        ← Clean, parsed output
│   ├── interim/          ← Intermediate chunks, embeddings
│   └── external/         ← Golden datasets, reference material
│
├── src/
│   ├── ingestion/        ← PDF/Excel/Password parsing
│   ├── chunking/         ← Text splitting strategies
│   ├── embedding/        ← Embedding model service
│   ├── retrieval/        ← Vector search, hybrid search
│   ├── generation/       ← LLM prompt + response
│   ├── evaluation/       ← RAGAS, metrics, golden set
│   └── api/              ← FastAPI endpoints
│
├── configs/              ← YAML configs (models, params)
├── notebooks/            ← Jupyter experiments
├── tests/                ← pytest
├── scripts/              ← One-off scripts (bulk index, migrate)
├── docs/                 ← Architecture docs, ADRs
├── models/               ← Local model weights (gitignored)
├── logs/                 ← Application logs
├── docker/               ← Dockerfiles, compose
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Phase 1: Data Ingestion & Exploration

we are first part understand the data if we are not understand data not working long time so create (requirements) file and few library to necessary before starting code.


```
bash

pip install --upgrade pip
pip install -r requirements.txt
```

### System Level Dependencies

```
bash

# Tesseract OCR (for scanned PDFs)
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin

# Poppler (PDF utilities)
sudo apt install poppler-utils

# LibreOffice (convert doc/xls to pdf if needed)
sudo apt install libreoffice
```

### ENV File Setup 

### .gitignore File setup

# Step 2: Data Exploration;


Our all data source and raw data in raw folder
i check documents type in raw folder

```
               📚 ABC Library — Data Inventory                
┏━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃          ┃       ┃   Total Size ┃           ┃     Avg Size ┃
┃ Format   ┃ Count ┃         (MB) ┃ Encrypted ┃         (MB) ┃
┡━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ (no ext) │     1 │         2.61 │     —     │         2.61 │
│ .db      │     2 │         0.10 │     —     │         0.05 │
│ .doc     │   117 │       450.41 │     —     │         3.85 │
│ .docx    │    24 │         2.66 │     —     │         0.11 │
│ .jpg     │     2 │         1.25 │     —     │         0.63 │
│ .mp3     │     2 │         0.57 │     —     │         0.28 │
│ .pdf     │   243 │       489.95 │   🔒 1    │         2.02 │
│ .png     │     2 │         0.12 │     —     │         0.06 │
│ .pps     │     2 │         6.98 │     —     │         3.49 │
│ .ppt     │     1 │         0.09 │     —     │         0.09 │
│ .pptx    │     3 │         3.76 │     —     │         1.25 │
│ .rar     │     2 │         4.03 │     —     │         2.01 │
│ .rtf     │     1 │       106.46 │     —     │       106.46 │
│ .txt     │     8 │         0.00 │     —     │         0.00 │
│ .xls     │    11 │         8.31 │     —     │         0.76 │
│ .xlsx    │    22 │         0.38 │     —     │         0.02 │
├──────────┼───────┼──────────────┼───────────┼──────────────┤
│ TOTAL    │   443 │      1077.68 │   🔒 1    │              │
└──────────┴───────┴──────────────┴───────────┴──────────────┘
```



