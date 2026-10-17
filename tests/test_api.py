import csv
import io
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import llm
from app.llm import extract_json
from app.scoring import script_share, term_hit

FACTS = { "product_name": "Tarakasi box","craft": "silver filigree", "material": "silver", "dimensions": "10 cm", "maker": "Ramesh", "village": "Cuttack"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import config
    import app.db as db
    import app.main as main

    # settings is frozen: swap the module-level object used by db/main instead
    new = config.Settings(data_dir=str(tmp_path))
    monkeypatch.setattr(db, "settings", new)
    monkeypatch.setattr(main, "settings", new)

    prompts = []

    def fake_generate(prompt, images):
        assert images, "images must be passed to the model"
        prompts.append(prompt)
        content = {
            "en": {"title": "Tarakasi box", "description": "A Tarakasi box, 10 cm wide."},
            "hi": {"title": "तारकशी डिब्बा", "description": "चांदी का तारकशी डिब्बा।"},
            "or": {"title": "ତାରକସି ବାକ୍ସ", "description": "ରୂପାର ତାରକସି ବାକ୍ସ।"},
        }
        return content, {"model": "fake", "latency_ms": 5, "prompt_tokens": 1, "completion_tokens": 1}

    monkeypatch.setattr(llm, "generate", fake_generate)
    c = TestClient(main.app)
    c.prompts = prompts
    return c


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (2000, 1500), "white").save(buf, format="JPEG")
    return buf.getvalue()


def _create(client, **over):
    return client.post("/listings", files=[("files", ("a.jpg", _jpeg(), "image/jpeg"))],
                       data={**FACTS, **over})


def test_health_and_page_load(client):
    assert client.get("/health").json()["ok"] is True
    r = client.get("/")
    assert r.status_code == 200
    assert "needs native review" in r.text
    assert "Export CSV" in r.text
    assert "CSV export failed" in r.text


def test_create_returns_facts_content_and_checks(client):
    r = _create(client)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["facts"] == {**FACTS, "gi": ""}
    assert d["content"]["or"]["title"] and "tags" not in d["content"]["en"]
    assert d["warnings"] == []
    assert d["terms"] == []
    # every seller fact reaches the model; missing ones are marked as not stated
    prompt = client.prompts[0]
    assert (
    "product_name=Tarakasi box; craft/technique=silver filigree; "
    "material=silver; dimensions=10 cm; maker=Ramesh; "
    "village=Cuttack; GI=not stated"
) in prompt


def test_unsupported_claims_and_missing_terms_are_reported(client, monkeypatch):
    def fake(prompt, images):
        body = {k: {"title": "t", "description": "Certified 99 cm box."} for k in ("en", "hi", "or")}
        return body, {}
    monkeypatch.setattr(llm, "generate", fake)
    d = _create(client).json()
    assert any("certification" in w.lower() for w in d["warnings"])
    assert any("99" in w for w in d["warnings"])
    assert d["terms"] == ["en: Tarakasi"]


def test_regenerate_feedback_history_flow(client):
    listing = _create(client).json()
    r2 = client.post(f"/listings/{listing['id']}/regenerate", json={"tone": "gift"})
    assert r2.status_code == 200
    assert r2.json()["id"] != listing["id"] and r2.json()["facts"]["village"] == "Cuttack"
    assert "warm and gift-oriented" in client.prompts[-1]

    fb = client.post(f"/listings/{listing['id']}/feedback", json={"rating": 5, "would_pay": True})
    assert fb.status_code == 200
    history = client.get("/listings").json()
    assert len(history) == 2 and history[0]["facts"]["craft"] == "silver filigree" and "warnings" in history[0]
    assert client.get(f"/listings/{listing['id']}").json()["facts"]["material"] == "silver"
    assert client.get("/listings/999").status_code == 404


def test_rejects_bad_input(client):
    assert client.post("/listings", files=[("files", ("a.txt", b"nope", "text/plain"))], data=FACTS).status_code == 400
    assert _create(client, material=" ").status_code == 400
    assert _create(client, tone="nonsense").status_code == 400
    five = [("files", (f"{i}.jpg", _jpeg(), "image/jpeg")) for i in range(5)]
    assert client.post("/listings", files=five, data=FACTS).status_code == 400


def test_model_failure_is_a_502_and_stores_no_listing(client, monkeypatch):
    def boom(prompt, images):
        raise llm.LLMError("down")
    monkeypatch.setattr(llm, "generate", boom)
    assert _create(client).status_code == 502
    assert client.get("/listings").json() == []


def test_purge_and_backup(client):
    import app.db as db
    from scripts.backup import backup

    listing = _create(client, craft="ikat").json()
    product = db.get_product(listing["product_id"])
    photo = json.loads(product["image_paths"])[0]

    # Not old enough yet: nothing is deleted
    assert db.purge_old_images(30) == 0
    # Age the product, then purge
    with db.connect() as c:
        c.execute("UPDATE products SET created_at='2000-01-01 00:00:00'")
    assert db.purge_old_images(30) == 1
    assert not Path(photo).exists()

    # Listing text survives, regenerate is refused with 410
    assert client.get(f"/listings/{listing['id']}").status_code == 200
    assert client.post(f"/listings/{listing['id']}/regenerate", json={"tone": "gift"}).status_code == 410

    # Backup is a readable copy with the data in it
    dest = backup(keep=2)
    assert sqlite3.connect(dest).execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 1


def test_csv_escapes_commas_quotes_newlines_and_keeps_hindi_odia(client):
    import app.main as main

    row = {c: f'{c}, "quoted"\nsecond line' for c in main.COLUMNS}
    row["odia_draft_title_needs_review"] = "ଢୋକରା"
    row["hindi_title"] = "ढोकरा"
    r = client.post("/csv", json=[row, row])
    assert r.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"), newline="")))
    assert rows[0] == main.COLUMNS and "needs_review" in rows[0][-1]
    assert len(rows) == 3 and rows[1] == [row[c] for c in main.COLUMNS]


def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": 2} thanks') == {"a": 2}
    with pytest.raises(llm.LLMError):
        extract_json("no json here")


def test_scoring():
    assert script_share("ତାରକସି ବାକ୍ସ", "or") > 0.95
    assert script_share("hello", "or") == 0.0
    assert term_hit("Beautiful Tarakasi work", "silver filigree", "en")
    assert not term_hit("plain box", "filigree", "en")


def test_eval_runs_on_the_facts_model(tmp_path, monkeypatch, client):
    from eval import run_eval

    img = tmp_path / "p.jpg"
    img.write_bytes(_jpeg())
    (tmp_path / "set.csv").write_text(f"id,craft,material,dimensions,images\np01,Tarakasi,,,{img}\n", encoding="utf-8")
    (tmp_path / "eval").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--label", "t", "--set", "set.csv"])
    run_eval.main()
    out = list(csv.DictReader(open(tmp_path / "eval" / "results_t.csv", encoding="utf-8")))
    assert out[0]["ok"] == "True" and out[0]["en_term_hit"] == "True"
