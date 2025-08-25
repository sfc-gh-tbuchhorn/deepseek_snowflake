from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
from openai import OpenAI
import os

app = FastAPI()

client = OpenAI(
    base_url="http://deepseek:8000/v1",
    api_key="dummy"  # No real auth needed internally
)

question = "What is the capital of the moon?"

@app.post("/echo")
async def echo(request: Request):
    data = await request.json()
    return data

@app.post("/relay")
async def relay_chat(request: Request):
    req = await request.json()
    prompt = req["data"][0][1]
    print("The recieved message is: ", req)
    print("The prompt is: ", prompt)

    response = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    messages=[
        {
            "role": "user",
            "content": prompt,
        }
    ],
    stream=False
    )
    print(response)
    content = response.choices[0].message.content
    print("\n The content is: ", content)
    return {"data": [[0, content]]}
