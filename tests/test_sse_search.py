import requests

s = requests.Session()
s.post("http://127.0.0.1:8000/auth/login", data={"password": "kgp2026"})

print("Connecting to /api/search SSE stream...")
with s.get("http://127.0.0.1:8000/api/search?role=product", stream=True, timeout=90) as resp:
    for line in resp.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data:"):
                print(decoded[:120])
                if "tier1_result" in decoded:
                    print(">>> Received tier1_result with YC and board jobs!")
                    break
