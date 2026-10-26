"""End-to-end verification script for AI Personal Tutor."""

import json
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def run_e2e():
    print("=== Step 1: Health check ===")
    res = requests.get(f"{BASE_URL}/health")
    print("Health:", res.status_code, res.json())
    assert res.status_code == 200

    print("\n=== Step 2: User Registration & Login ===")
    email = f"student_{int(time.time())}@example.com"
    reg_res = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": "secure_password_123"},
    )
    print("Register:", reg_res.status_code, reg_res.json())
    assert reg_res.status_code == 201
    token = reg_res.json()["access_token"]
    user_id = reg_res.json()["user_id"]
    headers = {"Authorization": f"Bearer {token}"}

    print("\n=== Step 3: Create Subject ===")
    subj_res = requests.post(
        f"{BASE_URL}/subjects",
        headers=headers,
        json={"name": "Classical Mechanics"},
    )
    print("Create Subject:", subj_res.status_code, subj_res.json())
    assert subj_res.status_code == 201
    subject_id = subj_res.json()["id"]

    print("\n=== Step 4: Upload Document ===")
    with open("eval/sample_physics_notes.pdf", "rb") as f:
        up_res = requests.post(
            f"{BASE_URL}/documents",
            headers=headers,
            data={"subject_id": subject_id},
            files={"file": ("sample_physics_notes.pdf", f, "application/pdf")},
        )
    print("Upload:", up_res.status_code, up_res.json())
    assert up_res.status_code == 201
    doc_id = up_res.json()["id"]

    print("\n=== Step 5: Wait for Ingestion to be Ready ===")
    status = "queued"
    for i in range(30):
        time.sleep(1)
        docs_res = requests.get(f"{BASE_URL}/documents", headers=headers, params={"subject_id": subject_id})
        docs = docs_res.json()
        doc = next((d for d in docs if d["id"] == doc_id), None)
        if doc:
            status = doc["status"]
            print(f"Poll {i+1}s: status={status}, pages={doc.get('pages')}, error={doc.get('error')}")
            if status == "ready":
                break
            if status == "failed":
                raise RuntimeError(f"Ingestion failed: {doc.get('error')}")

    assert status == "ready", f"Ingestion did not complete, status is {status}"

    print("\n=== Step 6: Grounded Question ('Explain Newton's second law') ===")
    chat_payload = {
        "question": "Explain Newton's second law",
        "subject_id": subject_id,
        "mode": "explain",
    }
    chat_res = requests.post(
        f"{BASE_URL}/chat",
        headers=headers,
        json=chat_payload,
        stream=True,
    )
    print("Chat status:", chat_res.status_code)
    assert chat_res.status_code == 200

    full_text = ""
    sources = []
    events = []

    current_event = "message"
    for line in chat_res.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event: "):
            current_event = line.replace("event: ", "").strip()
        elif line.startswith("data: "):
            data_val = line.replace("data: ", "").strip()
            if current_event == "token":
                token_text = json.loads(data_val)
                full_text += token_text
            elif current_event == "sources":
                sources = json.loads(data_val)
            elif current_event == "done":
                events.append("done")

    print(f"\nAssistant Response:\n{full_text}")
    print(f"\nSources ({len(sources)}):")
    for s in sources:
        print(f"  [{s['id']}] {s['filename']} p.{s['page_start']}: {s['section']}")

    assert "[S1]" in full_text or "[S" in full_text, "Response missing citation tag [S...]"
    assert len(sources) > 0, "Expected at least 1 cited source"

    print("\n=== Step 7: Out-of-domain Question ('What is the capital of Australia?') ===")
    ood_payload = {
        "question": "What is the capital of Australia?",
        "subject_id": subject_id,
        "mode": "explain",
    }
    ood_res = requests.post(
        f"{BASE_URL}/chat",
        headers=headers,
        json=ood_payload,
        stream=True,
    )
    assert ood_res.status_code == 200

    ood_text = ""
    current_event = "message"
    for line in ood_res.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event: "):
            current_event = line.replace("event: ", "").strip()
        elif line.startswith("data: "):
            data_val = line.replace("data: ", "").strip()
            if current_event == "token":
                ood_text += json.loads(data_val)

    print(f"\nOOD Response:\n{ood_text}")
    lower_ood = ood_text.lower()
    assert ("not found" in lower_ood or "not mentioned" in lower_ood or "don't contain" in lower_ood or "cannot answer" in lower_ood or "notes" in lower_ood), "Expected honest out-of-domain refusal"

    print("\n=== ALL E2E VERIFICATION CHECKS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    run_e2e()
