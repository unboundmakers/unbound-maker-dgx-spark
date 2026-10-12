# ASR helper: transcribe an audio file with local faster-whisper (small model, Chinese).
# Usage: asr.py <audio-file>  -> prints transcript to stdout
import sys

import av

_orig_open = av.open
def _compat_open(*args, **kwargs):
    kwargs.pop('metadata_errors', None)  # removed in av>=16, faster-whisper still passes it
    return _orig_open(*args, **kwargs)
av.open = _compat_open

from faster_whisper import WhisperModel

_model = None

def model():
    global _model
    if _model is None:
        _model = WhisperModel('small', device='cpu', compute_type='int8')
    return _model

def transcribe(path):
    segments, _ = model().transcribe(path, language='zh', beam_size=5, vad_filter=True,
                                     initial_prompt='以下是普通话简体中文转写，使用简体字。')
    return ''.join(s.text for s in segments).strip()

if __name__ == '__main__':
    print(transcribe(sys.argv[1]))
