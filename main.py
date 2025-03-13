import os
import json
import base64
import asyncio
import argparse
import websockets
from fastapi import FastAPI, WebSocket, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
from dotenv import load_dotenv
import uvicorn
import requests
import audioop
import wave

load_dotenv()

# configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
PHONE_NUMBER_FROM = os.getenv('PHONE_NUMBER_FROM')
DOMAIN = os.getenv('DOMAIN', 'localhost')
PORT = int(os.getenv('PORT', 5050))

SYSTEM_MESSAGE = (
    """
    you are a helpful assistant. you can provide information, answer questions, and help with tasks.
    """
)
VOICE = 'sage'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated',
    'response.done', 'input_audio_buffer.committed',
    'input_audio_buffer.speech_stopped', 'input_audio_buffer.speech_started',
    'session.created'
]
SHOW_TIMING_MATH = False

app = FastAPI()

if not OPENAI_API_KEY:
    raise ValueError('missing the openai api key. please set it in the .env file.')

# initialize a twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.get("/", response_class=JSONResponse)
async def index_page():
    return {"message": "twilio media stream server is running!"}

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """
    handle websocket connections between twilio and openai
    """
    print("client connected")
    await websocket.accept()

    # open wave files for inbound & outbound audio (mono, 16-bit, 8 khz)
    inbound_wav = wave.open("tests/inbound.wav", "wb")
    inbound_wav.setnchannels(1)
    inbound_wav.setsampwidth(2)
    inbound_wav.setframerate(8000)

    outbound_wav = wave.open("tests/outbound.wav", "wb")
    outbound_wav.setnchannels(1)
    outbound_wav.setsampwidth(2)
    outbound_wav.setframerate(8000)

    try:
        async with websockets.connect(
            "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17",
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            await initialize_session(openai_ws)

            # connection-specific state
            stream_sid = None
            latest_media_timestamp = 0
            last_assistant_item = None
            mark_queue = []
            response_start_timestamp_twilio = None

            async def receive_from_twilio():
                """
                receive g.711 μ-law audio from twilio, record to inbound.wav,
                and forward it to openai
                """
                nonlocal stream_sid, latest_media_timestamp
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        if data['event'] == 'media' and openai_ws.open:
                            latest_media_timestamp = int(data['media']['timestamp'])

                            # decode the inbound g.711 μ-law
                            ulaw_bytes = base64.b64decode(data['media']['payload'])
                            pcm_bytes = audioop.ulaw2lin(ulaw_bytes, 2)
                            # write real data to inbound
                            inbound_wav.writeframes(pcm_bytes)
                            # write matching silence to outbound
                            silence = b'\x00' * len(pcm_bytes)
                            outbound_wav.writeframes(silence)

                            # forward the base64 μ-law data to openai
                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": data['media']['payload']
                            }
                            await openai_ws.send(json.dumps(audio_append))

                        elif data['event'] == 'start':
                            stream_sid = data['start']['streamSid']
                            print(f"incoming stream has started {stream_sid}")
                            response_start_timestamp_twilio = None
                            latest_media_timestamp = 0
                            last_assistant_item = None

                        elif data['event'] == 'mark':
                            if mark_queue:
                                mark_queue.pop(0)

                except WebSocketDisconnect:
                    print("client disconnected.")
                    if openai_ws.open:
                        await openai_ws.close()

            async def send_to_twilio():
                """
                receive audio from openai, record to outbound.wav,
                then send that audio back to twilio
                """
                nonlocal stream_sid, last_assistant_item, response_start_timestamp_twilio
                try:
                    async for openai_message in openai_ws:
                        response = json.loads(openai_message)

                        if response['type'] in LOG_EVENT_TYPES:
                            print(f"received event: {response['type']}", response)
                        if response['type'] == 'session.updated':
                            print("session updated successfully:", response)

                        if response.get('type') == 'response.audio.delta' and 'delta' in response:
                            try:
                                # decode the base64 g.711 μ-law from openai
                                ulaw_bytes = base64.b64decode(response['delta'])

                                # convert μ-law to 16-bit pcm and write to outbound.wav
                                pcm_bytes = audioop.ulaw2lin(ulaw_bytes, 2)
                                # write real data to outbound
                                outbound_wav.writeframes(pcm_bytes)
                                # write matching silence to inbound
                                silence = b'\x00' * len(pcm_bytes)
                                inbound_wav.writeframes(silence)

                                # re-encode to base64 for twilio
                                audio_payload = base64.b64encode(ulaw_bytes).decode('utf-8')
                                audio_delta = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": audio_payload}
                                }
                                await websocket.send_json(audio_delta)

                                if response_start_timestamp_twilio is None:
                                    response_start_timestamp_twilio = latest_media_timestamp
                                    if SHOW_TIMING_MATH:
                                        print(f"setting start timestamp for new response: {response_start_timestamp_twilio}ms")

                                if response.get('item_id'):
                                    last_assistant_item = response['item_id']

                                await send_mark(websocket, stream_sid)

                            except Exception as e:
                                print(f"error processing audio data: {e}")

                        # trigger an interruption when caller speech is detected
                        if response.get('type') == 'input_audio_buffer.speech_started':
                            print("speech started detected.")
                            if last_assistant_item:
                                print(f"interrupting response with id: {last_assistant_item}")
                                await handle_speech_started_event()

                except Exception as e:
                    print(f"error in send_to_twilio: {e}")

            async def handle_speech_started_event():
                """
                handle interruption when the caller's speech starts
                """
                nonlocal response_start_timestamp_twilio, last_assistant_item
                print("handling speech started event.")
                if mark_queue and response_start_timestamp_twilio is not None:
                    elapsed_time = latest_media_timestamp - response_start_timestamp_twilio
                    if SHOW_TIMING_MATH:
                        print(f"calculating elapsed time for truncation: {latest_media_timestamp} - {response_start_timestamp_twilio} = {elapsed_time}ms")

                    if last_assistant_item:
                        if SHOW_TIMING_MATH:
                            print(f"truncating item with id: {last_assistant_item}, truncated at: {elapsed_time}ms")

                        truncate_event = {
                            "type": "conversation.item.truncate",
                            "item_id": last_assistant_item,
                            "content_index": 0,
                            "audio_end_ms": elapsed_time
                        }
                        await openai_ws.send(json.dumps(truncate_event))

                    await websocket.send_json({"event": "clear", "streamSid": stream_sid})

                    mark_queue.clear()
                    last_assistant_item = None
                    response_start_timestamp_twilio = None

            async def send_mark(connection, stream_sid):
                if stream_sid:
                    mark_event = {
                        "event": "mark",
                        "streamSid": stream_sid,
                        "mark": {"name": "responsePart"}
                    }
                    await connection.send_json(mark_event)
                    mark_queue.append('responsePart')

            # run both inbound and outbound tasks concurrently
            await asyncio.gather(receive_from_twilio(), send_to_twilio())

    finally:
        # ensure inbound.wav and outbound.wav have the same total frames
        inbound_frames = inbound_wav.getnframes()
        outbound_frames = outbound_wav.getnframes()

        # if inbound is shorter, add silence (0.0) for the difference, and vice versa
        if inbound_frames < outbound_frames:
            difference = outbound_frames - inbound_frames
            silent_pcm = b'\x00\x00' * difference
            inbound_wav.writeframes(silent_pcm)
        elif outbound_frames < inbound_frames:
            difference = inbound_frames - outbound_frames
            silent_pcm = b'\x00\x00' * difference
            outbound_wav.writeframes(silent_pcm)

        # close the wave files
        inbound_wav.close()
        outbound_wav.close()
        print("wav files closed.")

async def send_initial_conversation_item(openai_ws):
    """
    send initial conversation item if ai talks first
    """
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": """greet the user with 'hello there! i am an ai voice assistant 
                    powered by twilio and openai. how can i help you?'"""
                }
            ]
        }
    }
    await openai_ws.send(json.dumps(initial_conversation_item))
    await openai_ws.send(json.dumps({"type": "response.create"}))

async def initialize_session(openai_ws):
    """
    control the initial session with openai
    """
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    print('sending session update:', json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))

    # send initial greeting
    await send_initial_conversation_item(openai_ws)

async def check_number_allowed(to):
    """
    check if a number is allowed to be called
    """
    try:
        override_numbers = ['+16824035658'] 
        if to in override_numbers:
            return True

        incoming_numbers = client.incoming_phone_numbers.list(phone_number=to)
        if incoming_numbers:
            return True

        outgoing_caller_ids = client.outgoing_caller_ids.list(phone_number=to)
        if outgoing_caller_ids:
            return True

        return False
    except Exception as e:
        print(f"error checking phone number: {e}")
        return False

async def make_call(phone_number_to_call: str):
    """
    make an outbound call
    """
    if not phone_number_to_call:
        raise ValueError("please provide a phone number to call.")

    is_allowed = await check_number_allowed(phone_number_to_call)
    if not is_allowed:
        raise ValueError(f"the number {phone_number_to_call} is not recognized as a valid outgoing number or caller id!")

    outbound_twiml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Connect><Stream url="wss://{DOMAIN}/media-stream" /></Connect></Response>'
    )

    call = client.calls.create(
        from_=PHONE_NUMBER_FROM,
        to=phone_number_to_call,
        twiml=outbound_twiml
    )

    await log_call_sid(call.sid)

async def log_call_sid(call_sid):
    """
    log the call sid
    """
    print(f"call started with sid: {call_sid}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="run the ai voice assistant server.")
    parser.add_argument('--call', help="the phone number to call, e.g., '--call=+18005551212'")
    args = parser.parse_args()

    # if a phone number was provided, make the call
    if args.call:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(make_call(args.call))
    
    # start the server in any case
    uvicorn.run(app, host="0.0.0.0", port=PORT)