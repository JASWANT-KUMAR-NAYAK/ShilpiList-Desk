import csv
import io
import json
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import checks, db, llm
from .config import settings
from .prompts import FACTS, LANGS, TONES, build_prompt

app = FastAPI(title="ShilpiList", version="1.0.0")

MAX_FILES = 4
PAGE = Path(__file__).parent / "index.html"


def _prepare_image(raw: bytes) -> bytes:
    """Resize to max_image_px and re-encode as JPEG to keep RAM and latency low."""
    try:
        img = Image.open(io.BytesIO(raw))
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise HTTPException(400, "One of the files is not a valid image") from e
    img.thumbnail((settings.max_image_px, settings.max_image_px))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue()


def _validate_content(content: dict) -> dict:
    """Keep only the expected languages and fields; fill gaps so the UI never crashes."""
    clean = {}
    for lang in LANGS:
        block = content.get(lang) or {}
        clean[lang] = {
            "title": str(block.get("title", "")).strip(),
            "description": str(block.get("description", "")).strip(),
        }
    if not any(clean[lang]["description"] for lang in LANGS):
        raise llm.LLMError("Model returned an empty listing")
    return clean


def _out(listing: dict) -> dict:
    """Attach the seller's facts and the advisory checks to a stored listing."""
    product = db.get_product(listing["product_id"])
    facts = {k: product[k] for k in FACTS}
    listing["facts"] = facts
    listing["warnings"] = checks.unsupported(listing["content"], " ".join(facts.values()).lower())
    listing["terms"] = checks.missing_terms(listing["content"], facts["craft"])
    return listing


def _run(product, tone: str) -> dict:
    paths = json.loads(product["image_paths"])
    images = [Path(p).read_bytes() for p in paths if Path(p).exists()]
    if not images:
        raise HTTPException(410, "Photos for this product were deleted; upload them again")
    prompt = build_prompt({k: product[k] for k in FACTS}, tone)
    try:
        content, meta = llm.generate(prompt, images)
        content = _validate_content(content)
    except llm.LLMError as e:
        raise HTTPException(502, str(e)) from e
    listing_id = db.add_listing(product["id"], tone, content, meta)
    return _out(db.get_listing(listing_id))


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE.read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"ok": True, "model": settings.model, "endpoint": settings.base_url}


@app.post("/listings")
async def create_listing(
    files: list[UploadFile] = File(...),
    product_name: str = Form(""),
    craft: str = Form(""),
    material: str = Form(""),
    dimensions: str = Form(""),
    maker: str = Form(""),
    village: str = Form(""),
    gi: str = Form(""),
    tone: str = Form("simple"),
):
    facts = {k: v.strip() for k, v in zip(FACTS, (product_name, craft, material, dimensions, maker, village, gi))}
    if not (facts["craft"] and facts["material"] and facts["dimensions"]):
        raise HTTPException(400, "Craft, material and dimensions are required")
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(400, f"Upload 1 to {MAX_FILES} photos")
    if tone not in TONES:
        raise HTTPException(400, f"tone must be one of {list(TONES)}")

    upload_dir = Path(settings.data_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in files:
        jpeg = _prepare_image(await f.read())
        p = upload_dir / f"{uuid.uuid4().hex}.jpg"
        p.write_bytes(jpeg)
        paths.append(str(p))
    product_id = db.add_product(facts, paths)
    # The model call blocks for seconds; run it off the event loop.
    return await run_in_threadpool(_run, db.get_product(product_id), tone)


@app.get("/listings")
def list_listings(limit: int = 50):
    return [_out(d) for d in db.list_listings(min(max(limit, 1), 200))]


@app.get("/listings/{listing_id}")
def get_listing(listing_id: int):
    listing = db.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    return _out(listing)


class RegenerateBody(BaseModel):
    tone: str = "simple"


@app.post("/listings/{listing_id}/regenerate")
def regenerate(listing_id: int, body: RegenerateBody):
    if body.tone not in TONES:
        raise HTTPException(400, f"tone must be one of {list(TONES)}")
    listing = db.get_listing(listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    return _run(db.get_product(listing["product_id"]), body.tone)


class FeedbackBody(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    would_pay: bool | None = None
    edited_text: str | None = None


@app.post("/listings/{listing_id}/feedback")
def feedback(listing_id: int, body: FeedbackBody):
    if not db.get_listing(listing_id):
        raise HTTPException(404, "Listing not found")
    fid = db.add_feedback(listing_id, body.rating, body.would_pay, body.edited_text)
    return {"id": fid}


COLUMNS = ["product_name", "craft", "material", "dimensions", "maker", "village", "english_title", "english_description",
           "hindi_title", "hindi_description", "odia_draft_title_needs_review", "odia_draft_description_needs_review"]


@app.post("/csv")
def export_csv(rows: list[dict] = Body()):
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(COLUMNS)
    out.writerows([r[c] for c in COLUMNS] for r in rows)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8")  # BOM: Excel reads Hindi/Odia as UTF-8
