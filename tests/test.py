from pydub import AudioSegment
from pydub.playback import play

def overlay_audio(file_a, file_b, output_file):
    """
    overlay two wav files (same sample rate/channels) and export as `output_file`,
    then play the combined audio.
    """
    # load each wav file
    track_a = AudioSegment.from_wav(file_a)
    track_b = AudioSegment.from_wav(file_b)

    # overlay one on top of the other
    combined = track_a.overlay(track_b)

    # export to a new wav file
    combined.export(output_file, format="wav")

if __name__ == "__main__":
    # example usage
    overlay_audio("tests/inbound.wav", "tests/outbound.wav", "tests/call_log.wav")
