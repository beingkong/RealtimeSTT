from openai import OpenAI

client = OpenAI(
    api_key="EMPTY",
    base_url="http://localhost:8010/v1",
)

stream = client.chat.completions.create(
    model="Qwen/Qwen3-14B-AWQ",
    messages=[
        # {"role": "system", "content": "Please do not include <think> or any similar tags in your response."},这句不起作用对该模型
        {"role": "user", "content": "python版本号?/no_think"},#/no_think该标签有用
    ],
    max_tokens=32768,
    temperature=0.6,
    top_p=0.95,
    stream=True,
    extra_body={
    "top_k": 20,
    "chat_template_kwargs": {
        "enable_thinking": False
    }
},
)

print("Chat response:", end=" ", flush=True)
for chunk in stream:
    delta = chunk.choices[0].delta
    content = getattr(delta, "content", None) or getattr(delta, "reasoning_content", None)
    if content:
        print(content, end="", flush=True)
print()
