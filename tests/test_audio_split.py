import io
import os
import sys
import types
import pytest
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.modules.setdefault('openai', types.ModuleType('openai'))
pytest.importorskip('pydub')
from pydub import AudioSegment
from app.main import merge_audio_files_with_limit


def make_blob(seconds: int) -> bytes:
    seg = AudioSegment.silent(duration=seconds * 1000)
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return buf.getvalue()


def test_split_by_duration(tmp_path):
    audio_blobs = [make_blob(2) for _ in range(3)]
    paths = merge_audio_files_with_limit(audio_blobs, tmp_path, max_duration=5)
    assert len(paths) == 2
    durations = [AudioSegment.from_file(p).duration_seconds for p in paths]
    assert round(durations[0]) == 4
    assert round(durations[1]) == 2
