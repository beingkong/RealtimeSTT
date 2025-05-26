from openai import OpenAI

client = OpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8010/v1",
)

stream = client.chat.completions.create(
    model="Qwen/Qwen3-14B-AWQ",
    messages=[
        {"role": "user", "content": "9.11>9.8?"},
    ],
    max_tokens=32768,
    temperature=0.6,
    top_p=0.95,
    stream=True,
    extra_body={
    "top_k": 20,
},
)

print("Chat response:", end=" ", flush=True)
for chunk in stream:
    delta = chunk.choices[0].delta
    content = getattr(delta, "content", None) or getattr(delta, "reasoning_content", None)
    if content:
        print(content, end="", flush=True)
print()
