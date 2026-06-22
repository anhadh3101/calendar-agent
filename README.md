# Xpander API

A FastAPI project.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

The API will be available at http://127.0.0.1:8000.

- Interactive docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
