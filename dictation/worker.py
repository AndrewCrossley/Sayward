"""Whisper subprocess: no microphone, desktop access, or network use."""
import json
import ctypes
import os
import signal
import sys


def main():
    # Stop if the listener dies; leave no GPU worker orphan after a tray crash.
    ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0)
    if os.getppid() == 1:
        return
    from faster_whisper import WhisperModel
    device, cfg = sys.argv[1], json.loads(sys.argv[2])
    model = WhisperModel(
        cfg["model"], device=device,
        compute_type="int8_float16" if device == "cuda" else "int8",
        download_root=cfg["cache_dir"], local_files_only=True,
        cpu_threads=cfg["threads"], num_workers=1,
    )
    print(json.dumps({"ready": device}), flush=True)
    for line in sys.stdin:
        try:
            job = json.loads(line)
            segments, _ = model.transcribe(
                job["audio"], beam_size=5, vad_filter=True,
                language=cfg["language"] or None, condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            print(json.dumps({"text": text}), flush=True)
        except Exception as exc:
            print(json.dumps({"error": str(exc)}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), flush=True)
        sys.exit(1)
