import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:8000/chat',
    data=json.dumps({
        'question': 'What is the main problem addressed by the AI Model Governance Platform?',
        'subject_id': '59349ec0-8e6f-46e8-a292-513ee416ce53',
        'mode': 'explain'
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

with urllib.request.urlopen(req) as res:
    full_text = ""
    for line in res.read().decode().splitlines():
        if line.startswith("data: "):
            try:
                val = json.loads(line[6:])
                if isinstance(val, str):
                    full_text += val
            except Exception:
                pass

import sys
sys.stdout.buffer.write((full_text + "\n").encode("utf-8"))
