import datetime
import io
import os
import sys
import wave
import aiofiles
from dotenv import load_dotenv
from fastapi import WebSocket
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG", format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}", colorize=True)

async def save_audio(server_name: str, audio: bytes, sample_rate: int, num_channels: int):
    if len(audio) > 0:
        filename = f"recordings/{server_name}_recording_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        with io.BytesIO() as buffer:
            with wave.open(buffer, 'wb') as wf:
                wf.setnchannels(num_channels)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            async with aiofiles.open(filename, 'wb') as f:
                await f.write(buffer.getvalue())
        logger.info(f"merged audio saved to recordings/{filename}")
    else:
        logger.warning("no audio data to save!")
  
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
            "content": "You are Sarah, a call agent for NeuroSync Pharmaceutical Solutions. Initiate the conversation with the patient and ask them if they are interested in the clinical trial. Your goal is to screen potential participants for the Memory Enhancement Cognitive Support (MECS) clinical trial. Your goal is to have natural, engaging conversations with callers. Maintain a warm, friendly tone. Your output will be converted to audio so don't include special characters in your answers. Keep your responses concise and conversational."
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

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # start audio recording
        await audiobuffer.start_recording()
        # start conversation
        messages.append(
            {
                "role": "system",
                "content": "please introduce yourself to the user."
            }
        )
        await task.queue_frames([context_aggregator.user().get_context_frame()])
       
    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        # stop audio recording
        await task.cancel()

    @audiobuffer.event_handler("on_audio_data")
    async def on_audio_data(buffer, audio, sample_rate, num_channels):
        server_name = f"server_{websocket.client.port}"
        # save audio to file
        await save_audio(server_name, audio, sample_rate, num_channels)
    
    runner = PipelineRunner(handle_sigint=False, force_gc=True)
    await runner.run(task)