---
name: openrouter-til-embeddings
description: Build and troubleshoot the embeddings and similarities tables for this TIL Datasette site using OpenRouter. Use when generating related TILs, rebuilding tils.db, changing embedding models, fixing a missing similarities table, or updating the deployment workflow.
---

# OpenRouter TIL embeddings

Use the bundled `scripts/generate_embeddings.py` to replace only the `openai-to-sqlite embeddings` step. It calls OpenRouter and writes the same `embeddings(id, embedding)` table and BLOB representation expected by `openai-to-sqlite==0.4.x`.

Continue using `openai-to-sqlite similar` to calculate cosine similarities locally and populate `similarities`.

## Compatibility constraint

The installed `openai-to-sqlite==0.4.2` hardcodes 1,536 floats when decoding a vector. The script therefore defaults to OpenRouter model `openai/text-embedding-3-small` and rejects vectors that are not exactly 1,536-dimensional.

Do not mix vectors produced by different models, even when their dimensions match. When changing models, rebuild both derived tables.

## Initial or complete rebuild

Run from the repository root after `build_database.py` has populated `tils.db`:

```bash
export OPENROUTER_API_KEY="..."

.venv/bin/python \
  .agents/skills/openrouter-til-embeddings/scripts/generate_embeddings.py \
  tils.db --rebuild

.venv/bin/openai-to-sqlite similar tils.db --all --save
```

`--rebuild` drops both `embeddings` and `similarities` before regenerating embeddings. API calls are billable through OpenRouter.

## Incremental refresh

Without `--rebuild`, the script skips IDs already present in `embeddings`:

```bash
.venv/bin/python \
  .agents/skills/openrouter-til-embeddings/scripts/generate_embeddings.py tils.db

.venv/bin/openai-to-sqlite similar tils.db --all --save
```

Skipping by ID matches the original utility's behavior, but it does not detect changed article text. For a guaranteed refresh after content edits, use `--rebuild`. A future workflow optimization may delete embeddings only for changed paths before running the script.

## Verification

Never deploy until both derived tables exist and every TIL has an embedding:

```bash
.venv/bin/python - <<'PY'
import sqlite3

conn = sqlite3.connect("tils.db")
tables = {
    row[0] for row in conn.execute(
        "select name from sqlite_master where type = 'table'"
    )
}
assert "embeddings" in tables, "embeddings table is missing"
assert "similarities" in tables, "similarities table is missing"
til_count = conn.execute("select count(*) from til").fetchone()[0]
embedding_count = conn.execute("select count(*) from embeddings").fetchone()[0]
assert embedding_count == til_count, (embedding_count, til_count)
assert conn.execute("select count(*) from similarities").fetchone()[0] > 0
print(f"Verified {embedding_count} embeddings and a populated similarities table")
PY
```

Inspect sample output with:

```bash
.venv/bin/sqlite-utils rows tils.db similarities --limit 5 --table
```

## Production invariant

The deployment pipeline must run these steps in order:

1. Build or update `tils.db`.
2. Generate OpenRouter embeddings.
3. Generate and save similarities.
4. Run the verification check.
5. Deploy Datasette.

Treat a missing `similarities` table as a failed build, not a valid production state. The page template's related-content query expects that table, matching the original project design. Do not add a runtime missing-table fallback as a substitute for fixing the build pipeline.

## Optional OpenRouter attribution

The script supports OpenRouter's optional attribution headers:

```bash
export OPENROUTER_HTTP_REFERER="https://til.jiaqicai.com/"
export OPENROUTER_APP_NAME="TIL related content"
```

Use `--model` to select another model only if it returns exactly 1,536 dimensions and both derived tables are rebuilt.
