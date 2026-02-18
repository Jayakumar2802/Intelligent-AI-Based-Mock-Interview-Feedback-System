import requests
import os

HF_TOKEN = os.getenv("HF_TOKEN")

headers = {"Authorization": f"Bearer {HF_API_KEY}"}
data = {"inputs": "A futuristic robot walking in a neon-lit city"}
response = requests.post("https://api-inference.huggingface.co/models/damo-vilab/text-to-video-ms-1.7b", headers=headers, json=data)

with open("output.mp4", "wb") as f:
    f.write(response.content)
