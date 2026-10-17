# ShilpiList Desk

ShilpiList Desk helps people who list Odisha crafts for artisans create multilingual product listing drafts from photos and seller-provided facts. It generates drafts in **English, Hindi, and Odia**. Odia output requires native-speaker review before publishing.

Features include batch entry for up to 10 products through the web interface, separate product-name and craft/technique fields, photo uploads, tone selection, regeneration, listing history, feedback, CSV export, SQLite storage, and backup utilities.

## Current status

- **Automated tests:** 19 passed, 1 dependency warning in the latest recorded run.
- **Live-model evaluation:** 6 of 6 sample listings were generated successfully in the latest recorded evaluation.
- **Latest evaluation metrics:** English glossary hit rate 100%; Hindi 50%; Odia 50%; median latency 3.7 seconds.
- These results come from a small sample and are not proof of factual accuracy or translation quality. Glossary hit rates measure the presence of configured terms, not naturalness or correctness.
- Hindi and Odia glossary spellings remain unreviewed drafts. Do not treat them as approved until a native speaker verifies them.

## Setup (Windows, PowerShell)

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell prevents virtual-environment activation, you can run the environment's Python executable directly instead.

## Model endpoint

The app expects an OpenAI-compatible `/chat/completions` endpoint that accepts image input and JSON-mode responses. The default configuration is intended for local Ollama; other compatible endpoints can be configured through the environment settings.

Example for local Ollama:

```powershell
ollama pull gemma4
ollama list
```

Check `ollama list` for the exact model tag available on your machine.

Optional environment settings (defaults are documented in `.env.example`):

```powershell
$env:LLM_BASE_URL = "http://localhost:11434/v1"
$env:LLM_MODEL = "gemma4"
$env:LLM_API_KEY = "ollama"
$env:LLM_TIMEOUT_S = "300"
$env:DATA_DIR = "data"
```

Use the matching endpoint, model tag, and API key when configuring a hosted model service. Never commit API keys or other secrets to source control.

## Run

From the project directory:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

For each product, upload 1–4 photos and enter:

- **Product name** — the item being sold.
- **Craft / technique** — the craft or method used to make it.
- **Material** and **dimensions** — required product facts.
- **Maker / artisan**, **village / location**, and **GI status** — optional facts.

Choose a writing tone and click **Generate listings**. Generated drafts can be regenerated with another tone, rated, copied, or exported to CSV. History displays saved listings.

The web interface supports up to 10 products per batch. Products are generated sequentially, so processing a full batch may take some time.

Review every generated listing before using it. The system does not guarantee factual accuracy, and Odia text must be reviewed by a native speaker.

## Test

Run the automated test suite:

```powershell
python -m pytest -q
```

The tests mock the model endpoint. Passing tests establish that tested application behavior works; they do not establish real-model quality or translation accuracy.

## Accuracy checks and glossary

The app uses prompt instructions and heuristic checks to help reduce unsupported claims.

- **Unsupported-claim warnings:** flag some claims or numbers that may not be supported by the supplied facts. These checks are not proof that a statement is false or that an unflagged statement is correct.
- **Craft-term checks:** compare generated text with terms configured in `app/glossary.json`. They provide a limited terminology check, not a complete language-quality assessment.
- **Native review:** Hindi and Odia glossary terms are included in the generation prompt only when the relevant glossary entry has `"reviewed": true`. Keep unverified translations marked `false`.
- **Human review:** check every language for accuracy, natural wording, translated terminology, and unsupported claims before publishing.

The model is instructed to preserve the product name, craft/technique, materials, dimensions, and other supplied facts. Instructions and automated checks cannot guarantee compliance.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Serve the web interface |
| GET | `/health` | Return application/model endpoint status |
| POST | `/listings` | Create a listing from multipart form data |
| GET | `/listings` | Retrieve listing history |
| GET | `/listings/{id}` | Retrieve one listing |
| POST | `/listings/{id}/regenerate` | Regenerate a listing with a requested tone |
| POST | `/listings/{id}/feedback` | Store listing feedback |
| POST | `/csv` | Convert submitted listing rows to a CSV response |

The `/listings` endpoint accepts `files` (1–4 images), `product_name`, `craft`, `material`, `dimensions`, `maker`, `village`, `gi`, and `tone`. The web interface requires a product name; the server validates craft, material, and dimensions.

The `/regenerate` endpoint accepts JSON such as `{"tone": "gift"}`. Feedback accepts fields such as `rating`, `would_pay`, and `edited_text`.

## Storage, backups, and photo retention

Data is stored under `DATA_DIR` (default `data/`), including the SQLite database, uploaded photos, and backups.

Run the backup utility as needed:

```powershell
python -m scripts.backup --keep 7 --purge-days 30
```

The utility creates database backups and purges eligible old uploaded photos according to its retention settings. Listing text remains stored, but a listing whose photos have been purged cannot be regenerated until photos are uploaded again.

The app adds the `product_name` column automatically when opening a database created by the earlier schema. Back up the database before upgrading. Future schema changes may require additional migrations.

## Evaluation (optional)

Evaluation photos belong under `eval/images/`, and their relative paths should be listed in `eval/test_set.csv`. Fill in known materials and dimensions to make evaluations more representative.

Run the evaluation with:

```powershell
python -m eval.run_eval --label baseline --set eval/test_set.csv
```

The evaluation records listing-generation success, latency, script share, and craft glossary-term hits. Script share checks the expected writing system; glossary hits check configured terminology. Neither measure replaces a human review.

## Known limitations

- The app has no authentication. Do not expose it publicly without adding appropriate access controls.
- The batch limit of 10 is enforced by the web interface, not the API.
- CSV export does not include warning details. Odia columns are labelled to indicate that review is required.
- Spreadsheet software may interpret cells beginning with `=`, `+`, `-`, or `@` as formulas. Review exported data before using it in spreadsheets.
- Check the license and usage terms for the exact model configured. The repository's code license is documented in `LICENSE`.
