<h1>
<div align="center">
  <img alt="klix logo" width="250px" height="auto" src="/assets/klix.jpg">
</div>
<div align="center">

[![Klix AI](https://img.shields.io/badge/Klix-AI-blue)](https://klix-ai.com)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-00a393.svg)](https://fastapi.tiangolo.com/)
[![Twilio](https://img.shields.io/badge/Twilio-Voice-red.svg)](https://www.twilio.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>
</h1>

klix is a real time system that can be used to initiate a call from an AI agent to a predefined phone number.

it uses stt --> llm --> tts to analyse incoming audio, prepare a reply using an llm, and then reply using tts

under the hood, this package uses:

- [pipecat](https://github.com/pipecat-ai/pipecat) for the agent
- [cartesia](https://cartesia.ai/) for tts
- [deepgram](https://deepgram.com/) for transcription
- [openai](https://openai.com/) for the evaluator
- [twilio](https://www.twilio.com/) to initiate calls

## quick start

### set up:

```bash
git clone [github.com/ahitagnied/klix-ai](https://github.com/ahitagnied/klix-ai)
```

### set up your environment variables in a `.env` file

```bash
OPENAI_API_KEY=
DEEPGRAM_API_KEY=
CARTESIA_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
NGROK_AUTH_TOKEN=
```

### set up ngrok for local development

```bash
ngrok http 8765 --subdomain <your_subdomain>
```

### configure Twilio webhook

in your twilio phone number's configuration page:

1. go to "Voice Configuration" section
2. in the "A call comes in" section, select "Webhook"
3. enter your ngrok URL (e.g., http://<your_subdomain>.ngrok.io)
4. select "HTTP POST"
5. save your configuration

### set up the streams configuration

```bash
cp templates/streams.xml.template templates/streams.xml
```

edit `templates/streams.xml` and replace "wss://your-ngrok-url.ngrok.io/ws" with your ngrok URL (without https://). Your final URL should look like: `wss://<your_subdomain>.ngrok.io/ws`.

### run the server

```bash
python server.py
```

then, in a separate terminal window:

```bash
uvicorn server:app --reload
```

### make an outbound call

```bash
python caller.py +12345678910 --url <your_subdomain>.ngrok.io
```

replace `+12345678910` with the target phone number and `<your_subdomain>.ngrok.io` with your ngrok URL.

## how it works

klix consists of three main components:

### 1. server.py (FastAPI server)

the server handles WebSocket communication with Twilio and executes bot logic. it's responsible for handling real-time communication during calls.

```python
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
```

### 2. bot.py (Core Intelligence)

This contains the core intelligence of Klix, including pipeline management and integration with various AI services. It manages conversation flow and decision-making processes.

```python
async def run_bot(websocket: WebSocket, stream_sid: str, testing: bool):
    transport = FastAPIWebsocketTransport(
        websocket, 
        FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analuzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=TwilioFrameSerializer(stream_sid=stream_sid),
        )
    )

    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model ="gpt-4o")
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="57c63422-d911-4666-815b-0c332e4d7d6a", # Lori's voice
        push_silence_after_stopping=True
        )
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"), audio_passthrough=True)

    messages = [
        {
            "role": "system",
            "content": "you're a chill dude"
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # saves conversation in memory, add buffer_size for periodic callbacks
    audiobuffer = AudioBufferProcessor(user_continuous_stream=not testing)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            audiobuffer,
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            allow_interruptions=True,
        ),
    )
```

### 3. caller.py (Call Management)

A command-line tool for initiating outbound calls via the Twilio API, allowing for testing and evaluation of voice agents.

```python
def make_call(to_number, from_number, webhook_url, account_sid, auth_token):
    """initiate an outbound call using twilio api"""
    logger.info(f"initiating call to {to_number} from {from_number}")
    
    try:
        client = Client(account_sid, auth_token)
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            url=webhook_url,
        )
        logger.info(f"call initiated with sid: {call.sid}")
        return call.sid
    except Exception as e:
        logger.error(f"failed to initiate call: {e}")
        return None
```

## features

- **real-time transcription**: convert speech to text during calls
- **twilio integration**: handle phone calls with ease
- **development simplicity**: ngrok integration for local testing

## note

for questions or assistance, please open an issue in the repository.
