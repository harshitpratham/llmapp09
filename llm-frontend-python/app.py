import os

import httpx
from flask import Flask, request

API_URL = os.getenv("API_URL", "http://127.0.0.1:8090/api/chat")
APP_NAME = 'llmapp09'

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>__APP__</title>
  <style>
    body { font-family: Georgia, serif; margin: 40px auto; max-width: 760px; color: #1c1917; background: #faf7f2; }
    h1 { font-size: 28px; margin-bottom: 4px; }
    p.meta { color: #57534e; }
    textarea { width: 100%; min-height: 90px; font-size: 16px; padding: 10px; }
    button { background: #1d4ed8; color: white; border: 0; padding: 10px 16px; font-size: 16px; }
    .card { background: white; border: 1px solid #e7e5e4; padding: 16px; margin-top: 16px; }
    .label { font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase; color: #78716c; }
  </style>
</head>
<body>
  <h1>__APP__</h1>
  <p class="meta">Local workshop chat. The API is __API__.</p>
  <form method="post">
    <textarea name="message" required>__MESSAGE__</textarea>
    <p><button type="submit">Send</button></p>
  </form>
  __RESULT__
</body>
</html>
"""


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME, "api": API_URL}


@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    result = ""
    if request.method == "POST":
        message = request.form.get("message", "").strip()
        try:
            response = httpx.post(API_URL, json={"message": message}, timeout=180)
            response.raise_for_status()
            data = response.json()
            result = (
                '<div class="card"><div class="label">Reply</div>'
                f'<p id="reply">{data.get("reply", "")}</p>'
                f'<div class="label">Model</div><p id="model">{data.get("model", "")}</p>'
                f'<div class="label">Blocked</div><p id="blocked">{data.get("blocked", False)}</p>'
                "</div>"
            )
        except Exception as exc:
            result = f'<div class="card"><p id="reply">Request failed: {exc}</p></div>'
    html = (
        PAGE.replace("__APP__", APP_NAME)
        .replace("__API__", API_URL)
        .replace("__MESSAGE__", message)
        .replace("__RESULT__", result)
    )
    return html


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5050")))
