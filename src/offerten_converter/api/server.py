"""FastAPI entry point for the AMP Offerten Converter backend.

Start with:
    uvicorn offerten_converter.api.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_SRC = str(Path(__file__).resolve().parents[3])
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")

from offerten_converter.api.routes import router  # noqa: E402

app = FastAPI(
    title="AMP Sport Offerten Converter API",
    version="1.0.0",
    description="Converts supplier Excel offers into standardised AMP reseller offers.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
