# Quick test: send a drawing to local moondream via Ollama, ask for structured robot-part JSON.
import base64
import json
import sys
import urllib.request

PROMPT = """This is a child's drawing of an imaginary robot creature. Look at it and answer in JSON only, no other text:
{"body": "round|slim|stocky|quad", "ears": "cat|round|long|horn", "wings": "b5|b3|bat|none", "paws": "pad|claw|hoof|mitt", "tail": "long|fluff|stub|none", "color": "<main body color as hex like #F2A65A>", "creature": "<what animal it looks like, in Chinese>"}
Rules: quad=four legs; b5=many blade feathers, b3=a few blades, bat=membrane wings; pick the closest option; color must be the dominant body color."""

def analyze(path):
    img = base64.b64encode(open(path, 'rb').read()).decode()
    body = json.dumps({"model": "moondream", "prompt": PROMPT, "images": [img], "stream": False,
                       "options": {"temperature": 0.1}}).encode()
    req = urllib.request.Request('http://127.0.0.1:11434/api/generate', data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.load(r)
    return out.get('response', ''), out.get('total_duration', 0) / 1e9

if __name__ == '__main__':
    text, secs = analyze(sys.argv[1])
    print(f"--- {sys.argv[1]} ({secs:.1f}s)")
    print(text)
