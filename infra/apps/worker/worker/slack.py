import json
import urllib.request

def send_slack(webhook_url: str, text: str) -> None:
    payload = {"text": text}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        _ = resp.read()
