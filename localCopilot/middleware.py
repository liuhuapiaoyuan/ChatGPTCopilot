"""
All this file does is take the requests and forwrads them but changes a single parameter which is body['n']
  and also truncates prompts that are too long (because open soruce models have a shorter context size than Codex (GitHub Copilot)

More functionality should be added later such as keep track of context of multiple files and maintaining a user session,
  but this would need lots of experimenting.

    pip install -U httpx -U fastapi -U uvicorn -U websockets
    python middleware.py --port 8000

"""
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import requests
import os
from fastapi.middleware.cors import CORSMiddleware



from fastapi.responses import JSONResponse

# Check if the platform is not Windows
if os.name != 'nt':
    from signal import SIGPIPE, SIG_DFL, signal
    signal(SIGPIPE,SIG_DFL)

app = FastAPI()
# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)


#Return fake token response to Copilot extension
@app.get("/copilot_internal/v2/token")
def get_copilot_token():
    print('测试验证get_copilot_token()')
    #token value is just a random number
    content = {'token': '1316850460','accessToken': '1316850460',  'expires_at': 2600000000, 'refresh_in': 1800,'chat_enabled':True,}
    return JSONResponse(
        status_code=200,
        content=content
    )
 
@app.post("/openai/deployments/v1/chat/completions")
def azure_adapter(body: dict):
    print("azure_adapter request. body:",json.dumps(body))
    if "model" not in body:
      body['model'] = BACKEND_MODEL
    elif body['model']=='gpt-4':
      body['model'] = BACKEND_MODEL
    
    body['model'] = BACKEND_MODEL
    if "intent" in body: 
      del body['intent']


    global BACKEND_URI
    if BACKEND_URI is None:
        raise HTTPException(status_code=500, detail="Fatal Error, BACKEND_URI is not set")
    api = f"{BACKEND_URI}/v1/chat/completions" 
    headers = {
        "Accept": "application/json",
        "Content-type": "application/json",
        "Authorization":f"Bearer {BACKEND_URI_KEY}"
    }
    def code_completion_stream(api,body: dict,headers):
        # define the generator for streaming
        async def stream_content():
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    async with client.stream(
                        "POST",
                        api,
                        json=body,
                        headers=headers,
                    ) as response:
                        # Check if the response status is not successful
                        if response.status_code != 200:
                            raise HTTPException(
                                status_code=response.status_code,
                                detail="Failed to fetch from the target endpoint",
                            )
                        async for chunk in response.aiter_bytes():
                            yield chunk
            except httpx.ReadTimeout:
                print("A timeout occurred while reading data from the server.")

        return StreamingResponse(stream_content(), media_type="application/json")

    if "stream" in body and body["stream"]:
        return code_completion_stream(api,body,headers)
    else:
        response = requests.post(api, json=body, headers=headers)
        return JSONResponse(
            status_code=200,
            content=response.json()
        )


def githubCopilot2Chatgpt(body,model):
    language =  body['extra']['language']
    system_prompt = eval(f"f'''{PROMPT_TEMPLATE}'''")
    PREFIX_TAG = "abpxx6d04wxr"
    SUFFIX_TAG = "as65d4a56z1"
    prompt =  body['prompt']
    suffix =  body['suffix']
 
    target_body =  {
       "model": model,
       "messages": [
        {"role": "system", "content":"You are an AI programming assistant.\nWhen asked for your name, you must respond with \"GitHub Copilot\".\nFollow the user's requirements carefully & to the letter.\nThe user has a javascript file opened in a code editor.\nThe user includes some code snippets from the file.\nEach code block starts with ``` and // FILEPATH.\nAnswer with a single javascript code block.\nIf you modify existing code, you will use the // BEGIN: and // END: markers.\nYour expertise is strictly limited to software development topics.\nFollow Microsoft content policies.\nAvoid content that violates copyrights.\nFor questions not related to software development, simply give a reminder that you are an AI programming assistant.\nKeep your answers short and impersonal."},
        {"role":"user","content":f"""I have the following code above the selection:
```javascript:
// BEGIN: {PREFIX_TAG}
{prompt}
// END: {PREFIX_TAG}```""" },
        {"role":"user","content":f"""I have the following code below the selection:
```javascript:
// BEGIN: {SUFFIX_TAG}
{suffix}
// END: {SUFFIX_TAG}```""" },
{"role":"user","content":"继续完成abpxx6d04wxr"}
         
       ],
       "temperature":0,
       "top_p": body['top_p'] , 
       "stream":body['stream'],
   #    "stop":body['stop'],
       "n":body['n'],
    #    "logit_bias":body['logit_bias'],
       "max_tokens":body['max_tokens'],
    }    
    with open("target_body.txt", "w") as file:
      json.dump(target_body, file)
    return target_body


@app.post("/v1/engines/codegen/completions")
async def code_completion(body: dict):
    print("github copilot :",json.dumps(body))
    
    body["n"] = 1
    # if "max_tokens" in body:
   # print("making request. body:", {k: v for k, v in body.items() if k != "prompxxt"})

    #     del body["max_tokens"]

    # FIXME: this is just a hardcoded number, but this should actually use the tokenizer to truncate
    # body["prompt"] = body["prompt"][-4000:]
    # print("making request. body:", {k: v for k, v in body.items() if k != "prompt"})

    global BACKEND_URI
    if BACKEND_URI is None:
        raise HTTPException(status_code=500, detail="Fatal Error, BACKEND_URI is not set")


    def code_completion_stream(body: dict):
        # define the generator for streaming
        async def stream_content():
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    body["n"] = 1
                    async with client.stream(
                        "POST",
                        f"{BACKEND_URI}/v1/chat/completions",
                        json=githubCopilot2Chatgpt(body,BACKEND_MODEL),
                        headers={
                            "Accept": "application/json",
                            "Content-type": "application/json",
                            "Authorization":f"Bearer {BACKEND_URI_KEY}"
                        },
                    ) as response:
                        # Check if the response status is not successful
                        if response.status_code != 200:
                            # await response.aread()  # 异步读取响应内容
                            # response_text = response.text
                            # print("错误的响应：",response_text)
                            raise HTTPException(
                                status_code=response.status_code,
                                detail="Failed to fetch from the target endpoint",
                            )
                        # Stream the response content
                        async for chunk in response.aiter_bytes():
                            # print('getting chunk')
                           # print(f"{chunk=}")
                            yield chunk
            except httpx.ReadTimeout:
                print("A timeout occurred while reading data from the server.")

        return StreamingResponse(stream_content(), media_type="application/json")

    if "stream" in body and body["stream"]:
        return code_completion_stream(body)
    else:
        raise NotImplementedError

def main():
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--backend", type=str, default="https://oneapi.lionsn.com")
    parser.add_argument("--backend_key", type=str, default="sk-f3o7ZBk08dBA7AX6684bFe75Df7d4e9494304998339e9d91")
    parser.add_argument("--backend_model", type=str, default="gpt-3.5-turbo-16k")
    parser.add_argument("--prompt_file", type=str, default="./prompts/1.txt")
    args = parser.parse_args()
    
    
    global BACKEND_URI
    global BACKEND_URI_KEY
    global BACKEND_MODEL
    global PROMPT_TEMPLATE
    BACKEND_URI = args.backend
    BACKEND_MODEL = args.backend_model  
    BACKEND_URI_KEY = args.backend_key
    # 读取模板
    with open(args.prompt_file , "r") as file:
        PROMPT_TEMPLATE = file.read()
    


    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
