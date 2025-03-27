from pydub import AudioSegment, silence
import openai
import wave
import io
import os

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def detect_voice_segments(wav_path, min_silence_len=1500, silence_thresh=-40):
    """
    detects segments of speech (non-silent audio) in a wav file

    args:
        wav_path (str): path to the input .wav file
        min_silence_len (int): minimum length of silence (in milliseconds) that will be used to separate speech segments.
        silence_thresh (int): silence threshold in decibels. audio quieter than this will be considered silent.

    returns:
        list of tuples: each tuple is (start_time, end_time) in seconds for a detected speech segment
    """
    audio = AudioSegment.from_wav(wav_path)

    # detect non-silent chunks [(start_ms, end_ms), ...]
    chunks = silence.detect_nonsilent(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)

    # convert ms to seconds
    return [(start / 1000, end / 1000) for start, end in chunks]

def extract_audio_segment(wav_path, start, end):
    """
    extracts a segment from a wav file between start and end times (in seconds)

    args:
        wav_path (str): path to the input wav file
        start (float): start time in seconds
        end (float): end time in seconds

    returns:
        io.BytesIO: in-memory wav file of the extracted audio segment
    """
    audio = AudioSegment.from_wav(wav_path)
    segment = audio[start * 1000:end * 1000]
    out = io.BytesIO()
    segment.export(out, format="wav")
    out.seek(0)
    out.name = "chunk.wav"
    return out

def transcribe_turns(wav_path, segments, speaker):
    """
    transcribes alternating speaker turns from audio segments using openai whisper

    args:
        wav_path (str): path to the wav file containing the full conversation
        segments (list of tuples): list of (start, end) timestamps (in seconds) for each speech segment
        api_key (str): openai api key for accessing whisper api

    returns:
        list of str: transcribed lines in the format 'ai: ...' or 'user: ...'
    """
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    transcript = []

    for start, end in segments:
        wav_chunk = extract_audio_segment(wav_path, start, end)

        try:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_chunk,
            )
            text = resp.text.strip()
        except Exception as e:
            text = f"[error: {e}]"

        line = f"{speaker}: {text}"
        transcript.append(line)

    return transcript

if __name__ == "__main__":
    user_timestamps = detect_voice_segments("tests/inbound.wav") 
    user_transcript = transcribe_turns("tests/inbound.wav", user_timestamps, speaker="user") # <-- list of user responses

    ai_timestamps = detect_voice_segments("tests/outbound.wav") 
    ai_transcript = transcribe_turns("tests/outbound.wav", ai_timestamps, speaker="ai") # <-- list of ai responses

    transcript_path = "transcript.txt"

    # check if file exists
    if not os.path.exists(transcript_path):
        print(f"creating file: {transcript_path}")
        open(transcript_path, 'w').close()  # creates an empty file

    def alternate_merge(list1, list2): 
        result = []
        max_len = max(len(list1), len(list2))
        
        for i in range(max_len):
            if i < len(list1):
                result.append(list1[i])
            if i < len(list2):
                result.append(list2[i])
        
        return result

    transcript = alternate_merge(ai_transcript, user_transcript) # <-- list of alternating ai and user responses

    # write content to it
    with open(transcript_path, "w") as f:
        f.write("\n".join(transcript))

    print("transcription complete.")