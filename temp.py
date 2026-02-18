import google.generativeai as genai

genai.configure(api_key="AIzaSyAsGLYqoUMQC4h862DRI7NLqdJTJp7VvAI")

for model in genai.list_models():
    print(model.name)

model = genai.GenerativeModel("models/gemini-2.5-flash")

resp = model.generate_content(contents="Explain how AI works in a few word")

print(resp.text)
