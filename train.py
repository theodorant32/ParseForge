"""
train.py — Train the ML Intent Classifier (Semantic Embedding Upgrade)

This script reads training_data.jsonl and trains a Logistic Regression model
on top of Semantic Embeddings (all-MiniLM-L6-v2) to classify user intent.
"""

import json
from pathlib import Path

import joblib
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression


def train_model():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    training_file = data_dir / "training_data.jsonl"
    model_file = data_dir / "intent_model.pkl"

    if not training_file.exists():
        print(f"❌ Cannot find training data at {training_file}")
        return

    print("1. Loading training data...")
    texts = []
    labels = []
    
    with open(training_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            texts.append(record["text"])
            labels.append(record["intent"])

    print(f"   Loaded {len(texts)} training examples.")

    print("\n2. Initializing Semantic Embedder (all-MiniLM-L6-v2)...")
    # This automatically downloads the ~80MB model if not cached
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    print("\n3. Encoding training sentences into 384-dimensional concepts...")
    X_embeddings = embedder.encode(texts, show_progress_bar=True)

    print("\n4. Training Logistic Regression directly on concepts...")
    model = LogisticRegression(C=0.5, class_weight="balanced", max_iter=1000, random_state=42)
    model.fit(X_embeddings, labels)

    acc = model.score(X_embeddings, labels)
    print(f"\n   Training accuracy: {acc:.0%}")

    print(f"\n5. Saving intelligent classifier to {model_file}...")
    joblib.dump(model, model_file)
    print("✅ Training complete. The MLParser will now load this model automatically.")


if __name__ == "__main__":
    train_model()
