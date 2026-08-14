from src.localai_client import LocalAIClient
try:
    client = LocalAIClient(model="zero-gemma4-e4b-openzero-q5-k-m")
    resp = client.chat(prompt="Hello", system="System prompt")
    print("Success:", resp)
except Exception as e:
    print("Error:", e)
