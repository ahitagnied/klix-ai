import argparse
import json
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse
from bot import run_bot

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/twiml")
async def twiml_response(request: Request):
    """Return TwiML instructions when Twilio connects the call"""
    return HTMLResponse(
        content=open("templates/streams.xml").read(),
        media_type="application/xml"
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    start_data = websocket.iter_text()
    await start_data.__anext__()
    call_data = json.loads(await start_data.__anext__())
    print("Call data: ", call_data, flush=True)
    stream_sid = call_data.get("start", {}).get("streamSid")
    print("Stream SID: ", stream_sid, flush=True)
    print("WebSocket connection established", flush=True)
    await run_bot(websocket, stream_sid, app.state.testing)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Outbound Twilio calls server.")
    parser.add_argument(
        "--testing",
        action="store_true",
        help="Run the server in testing mode.",
        default=False
    )
    args, _ = parser.parse_known_args()
    app.state.testing = args.testing
    uvicorn.run(app, host = "0.0.0.0", port = 8765)