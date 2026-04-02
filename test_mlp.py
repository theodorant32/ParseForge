import joblib
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer("all-MiniLM-L6-v2")
model = joblib.load("data/intent_model.pkl")

emb = embedder.encode(["I need help with this weekend"])
probas = model.predict_proba(emb)[0]
print(probas)
print(model.classes_[probas.argmax()])
print("Done!")
