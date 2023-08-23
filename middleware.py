"""
All this file does is take the requests and forwrads them but changes a single parameter which is body['n']
  and also truncates prompts that are too long (because open soruce models have a shorter context size than Codex (GitHub Copilot)

More functionality should be added later such as keep track of context of multiple files and maintaining a user session,
  but this would need lots of experimenting.
"""

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import httpx


app = FastAPI()


@app.post("/v1/engines/codegen/completions")
async def code_completion(body: dict):
    body["n"] = 1
    if "max_tokens" in body:
        del body["max_tokens"]

    print("making request. body:", {k: v for k, v in body.items() if k != "prompt"})

    def code_completion_stream(body: dict):
        # define the generator for streaming
        async def stream_content():
            async with httpx.AsyncClient() as client:
                for i in range(body["n"]):
                    # FIXME: this is just a hardcoded number, but this should actually use the tokenizer to truncate
                    body["prompt"] = body["prompt"][-2048:]
                    async with client.stream(
                        "POST",
                        "http://localhost:5001/v1/codegen/completions",
                        json=body,
                        headers={
                            "Accept": "application/json",
                            "Content-type": "application/json",
                        },
                    ) as response:
                        # Check if the response status is not successful
                        if response.status_code != 200:
                            raise HTTPException(
                                status_code=response.status_code,
                                detail="Failed to fetch from the target endpoint",
                            )

                        # Stream the response content
                        async for chunk in response.aiter_bytes():
                            # print('getting chunk')
                            print(f"{chunk=}")
                            yield chunk

        return StreamingResponse(stream_content(), media_type="application/json")

    def code_completion_nostream(body: dict):
        response = requests.post(
            "http://localhost:5001/v1/engines/codegen/completions",
            {
                "method": "POST",
                "headers": {
                    "Accept": "application/json",
                    "Content-type": "application/json",
                },
                "body": body,
            },
        )
        print("response", response, response.content)
        return response.content

    if "stream" in body and body["stream"]:
        return code_completion_stream(body)
    else:
        return "data: " + code_completion_nostream(body)


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)
