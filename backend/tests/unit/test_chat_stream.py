import json

from app.api.chat import _format_sse


def test_format_sse_frames_named_json_event():
    frame = _format_sse("delta", {"text": "hello\nworld"})

    assert frame.startswith("event: delta\n")
    assert frame.endswith("\n\n")
    data_line = next(line for line in frame.splitlines() if line.startswith("data:"))
    assert json.loads(data_line.removeprefix("data:").strip()) == {"text": "hello\nworld"}
