"""Day-1 check: does your local Gemma write usable Odia and Hindi for your products?

Usage (from the repo root, with Ollama running and a Gemma 4 model pulled):
    python -m scripts.day1_check --craft filigree photo1.jpg photo2.jpg
Run it on 5 different products and keep the output for your write-up.
"""
import argparse
import io
import json

from PIL import Image

from app import llm
from app.config import settings
from app.main import _validate_content
from app.prompts import build_prompt
from app.scoring import score_listing


def load_small(path: str) -> bytes:
    img = Image.open(path).convert("RGB")
    img.thumbnail((settings.max_image_px, settings.max_image_px))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--craft", required=True)
    ap.add_argument("--material", default="")
    ap.add_argument("--dimensions", default="")
    ap.add_argument("--tone", default="simple")
    ap.add_argument("images", nargs="+")
    args = ap.parse_args()

    prompt = build_prompt({"craft": args.craft, "material": args.material, "dimensions": args.dimensions}, args.tone)
    content, meta = llm.generate(prompt, [load_small(p) for p in args.images])
    content = _validate_content(content)
    print(json.dumps(content, ensure_ascii=False, indent=2))
    print("\nmeta:", meta)
    print("scores:", score_listing(content, args.craft))
    print(
        "\nRead the scores like this: *_script_share should be above 0.8 for hi and or "
        "(low means the model drifted into another language or script)."
    )


if __name__ == "__main__":
    main()
