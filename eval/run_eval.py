"""Evaluation script for retrieval recall and accuracy on a golden set."""

import argparse
import json
import os
import sys

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.rag.retrieve import hybrid_search
from app.rag.rerank import rerank
from app.auth import DEMO_USER_ID


def evaluate(golden_path: str, user_id: str = DEMO_USER_ID, subject_id: str | None = None, k: int = 5):
    hits = 0
    total = 0
    results = []

    print(f"--- Running Retrieval Evaluation on: {golden_path} (Recall@{k}) ---")
    with open(golden_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            question = ex["question"]
            expected_file = ex.get("expected_file")
            expected_page = ex.get("expected_page")
            target_subject = ex.get("subject_id", subject_id)

            candidates = hybrid_search(user_id, question, target_subject, k_each=30, k_final=20)
            top = rerank(question, candidates, top_n=k)

            found = any(
                c["filename"] == expected_file
                and (expected_page is None or (c["page_start"] <= expected_page <= c["page_end"]))
                for c in top
            )

            status = "PASS" if found else "MISS"
            print(f"[{status}] Q: {question}")
            if not found and top:
                print(f"       Top match retrieved: {top[0]['filename']} (pp. {top[0]['page_start']}-{top[0]['page_end']}) score={top[0].get('score', 0):.3f}")

            hits += int(found)
            total += 1
            results.append({"question": question, "pass": found, "top": top})

    recall = (hits / total) if total > 0 else 0.0
    print(f"\n==========================================")
    print(f"Final Recall@{k}: {hits}/{total} = {recall:.1%}")
    print(f"==========================================")
    return recall, results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run retrieval evaluation against a golden set")
    parser.add_argument("golden_path", nargs="?", default="eval/golden.jsonl", help="Path to golden.jsonl")
    parser.add_argument("--k", type=int, default=5, help="Top-K cutoff for recall")
    parser.add_argument("--subject_id", type=str, default=None, help="Optional subject ID")
    args = parser.parse_args()

    evaluate(args.golden_path, k=args.k, subject_id=args.subject_id)
