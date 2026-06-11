from sentence_transformers import SentenceTransformer
import numpy as np

model=SentenceTransformer("BAAI/bge-large-en-v1.5")

def cosine_sim(a,b):
    return np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))

def get_embedding_hints(schema_headings,report_headings):
    hints=[]
    used_report_headings = set()
    all_embeddings = model.encode(schema_headings + report_headings)
    schema_embeddings = all_embeddings[:len(schema_headings)]
    report_embeddings = all_embeddings[len(schema_headings):]
    candidates = []
    for i,sh in enumerate(schema_headings):
        scores=[cosine_sim(schema_embeddings[i],report_embeddings[j]) for j in range(len(report_headings))]
        best_idx=np.argmax(scores)
        best_score=scores[best_idx]
        candidates.append((best_score, i, best_idx))

    for best_score, i, best_idx in sorted(candidates, reverse=True):
        rh = report_headings[best_idx]
        if best_score > 0.75 and rh not in used_report_headings:
            hints.append({
                "schema_heading":schema_headings[i],
                "report_heading":rh,
                "method":"embedding",
                "similarity": round(float(best_score), 4)
            })
            used_report_headings.add(rh)
    return hints