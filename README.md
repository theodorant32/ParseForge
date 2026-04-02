# 🏦 ParseForge

> *"The wolf doesn't care about your messy input. He just wants the deal closed."*

I've always been fascinated by Wall Street. Not the wealth, but the **machine**. The way raw, chaotic information is converted into high-stakes decisions instantly. 

Those who win have a system. **ParseForge is that system for your unstructured data.**

It takes messy free-form text, runs it through a local Neural Network (Semantic Embeddings), validates it, scores it 0–100 like a risk model, and executes a routing decision instantly. 

---

## 🔄 The Trading Floor

```
Raw Input (the noise)
   ↓
🧠 ML Parser        — Maps semantic meaning to intent (gig, project, help) using SentenceTransformers
   ↓
📦 Schema & Check   — Enforces strict types and applies business rules
   ↓
🧩 Enricher         — Infers urgency, adds metadata and context
   ↓
📈 Decision Engine  — Scores request (0–100) → decide: MATCH / QUEUE / CLARIFY / REJECT
```

Every trade has a paper trail. So does every ParseForge request.

---

## 🚀 Quick Start

**1. Install**
```bash
pip install -r requirements.txt
```

**2. Enter the Interactive Trading Floor (REPL)**
This is the fastest way to test exactly how the pipeline reacts to unstructured input.
```bash
python cli.py interactive
```

**3. Single Execution or Batch**
```bash
python cli.py run "Need 2 engineers for a startup project ASAP"
python cli.py batch tests/fixtures/inputs.json
```

---

## 🧠 The AI Model

We skipped fragile "word keyword matching". ParseForge runs a fully offline **Semantic Meaning** neural network (`all-MiniLM-L6-v2`) via `sentence-transformers`. 

It inherently understands the English language. It knows "plumber" relates to a "task" and "collaboration" relates to a "project" without you hard-coding rules for it. 

**Want to teach it something new?**
1. Add examples to `data/training_data.jsonl`.
2. Run `python train.py`.
3. The pipeline recompiles instantly and understands your custom workflow.

---

## 🌐 The API (Automated Desk)

Want to route data from another app? ParseForge ships with a FastAPI layer.

```bash
python cli.py serve
```
Send a request to the active floor:
```bash
curl -X POST http://localhost:8000/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"text": "Find me a freelance designer this weekend"}'
```

---

## ⚖️ The Risk Desk (Scoring)

Every request gets a risk score based on clarity. 

| Score | Action | What It Means |
|---|---|---|
| ≥ 70 | 🟢 `MATCH` | Perfect signal. Ready to execute. |
| 50–69 | 🔵 `QUEUE` | Good signal. Place in pending queue. |
| 30–49 | 🟡 `CLARIFY` | Need more info before routing. |
| < 30 | 🔴 `REJECT` | Noise. Walk away. |

---

> *"It's not about the money. It's about the game."*
> — ParseForge.
