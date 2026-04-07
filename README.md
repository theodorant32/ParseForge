# ParseForge

A pipeline that converts unstructured text into structured decisions.

## How it works

```
Input → Parse → Validate → Enrich → Decide
```

1. **Parse** - Extracts intent, topic, team_size, timeframe using regex + keyword matching
2. **Validate** - Checks logical correctness (future timeframe, valid team size)
3. **Enrich** - Adds metadata and infers urgency from keywords
4. **Decide** - Scores 0-100 and routes: MATCH / QUEUE / CLARIFY / REJECT

## Quick Start

```bash
pip install -r requirements.txt
```

```bash
# Interactive mode
python cli.py interactive

# Single run
python cli.py run "Need 2 engineers for a startup project ASAP"

# Batch mode
python cli.py batch tests/fixtures/inputs.json

# Start API server
python cli.py serve
```

## ML Parser

Train a local ML model on semantic embeddings:

```bash
# Add examples to data/training_data.jsonl
python train.py
```

The ML parser uses `sentence-transformers` (all-MiniLM-L6-v2) and scikit-learn.

## Scoring

| Score | Action |
|-------|--------|
| ≥ 70  | MATCH  |
| 50-69 | QUEUE  |
| 30-49 | CLARIFY|
| < 30  | REJECT |
