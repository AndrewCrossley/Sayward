"""Offline, insertion-only English punctuation. Downloads are explicit setup."""
import hashlib
from contextlib import contextmanager
import json
from pathlib import Path
import re
import tempfile
import sys
from urllib.request import urlopen

MODEL_REPO = 'Horizon-Labs/punctuation-restoration-small'
MODEL_REVISION = 'b76fda22746a0f7778594493f0ad50f82dc4ae8a'
# Pinned public Apache-2.0 weights; runtime never downloads code or calls the Hub.
MODEL_FILES = {
    'model.onnx': ('onnx/model_quantized.onnx', 268414381, '5679870be92c7fa47c9be9b2872fac389ef28d43d2c33f35e1315b93a82f4ace'),
    'tokenizer.json': ('tokenizer.json', 34363286, 'f34b44a6dc8a0eef651bfa10e8325057530152606a69d9c3b6ae02efb1558f0a'),
    'config.json': ('config.json', 2110, 'f457c77954f0720ff2c0624b92714fb551bd19c42fba0625ee7af1740df49e05'),
}
WORDS = re.compile(r'\S+')
LINK = re.compile(r'(?:https?://|www\.)\S+|[^\s@]+@[^\s@]+\.[^\s@]+|(?:[A-Za-z]:[\\/]|/|~/)\S+', re.I)
PROTECTED = re.compile(LINK.pattern+r'|`[^`]*`|\b[\w.$:]+\([^()\r\n]*\)|\b[\w.-]+\.(?:json|yaml|yml|toml|py|js|ts|sql|csv|txt|md|log|exe|dll|onnx|wav|mp3|html|xml|sh|ps1)\b|\b(?:[A-Za-z]\.){2,}|\b(?:Mr|Mrs|Ms|Dr|Prof|etc)\.', re.I)
CLOSERS = '\"\'”’)]}'
QUOTES = '\"\'”’'
TERMINAL = '.!?…'
QUESTION = re.compile(r'^(?:(?:can|could|will|would|should|do|does|did|have|has|had|is|are|was|were|am|may|might|must)\s+(?:i|you|he|she|it|we|they|this|that|these|those|there)\b|(?:what|when|where|why|how|who|which)\s+(?:is|are|was|were|do|does|did|can|could|will|would|should|have|has)\b)', re.I)


def model_ready(directory):
    directory = Path(directory)
    return all((directory/name).is_file() and (directory/name).stat().st_size == data[1] for name, data in MODEL_FILES.items())


def _valid(path, size, digest):
    if not path.is_file() or path.stat().st_size != size:
        return False
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == digest


@contextmanager
def _download_lock(directory):
    # OS locks are released even when Quit interrupts the daemon downloader.
    with (directory/'punctuation-download.lock').open('a+b') as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b'\0');lock.flush()
        lock.seek(0)
        try:
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('Another punctuation download is already in progress') from error
        try:
            yield
        finally:
            lock.seek(0)
            if sys.platform == 'win32':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def download_model(directory):
    """User-triggered setup only; install integrity-checked files atomically."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with _download_lock(directory):
        # Only the lock owner may retire leftovers from an interrupted setup.
        for stale in directory.glob('sayward-punctuation-*.part'):
            stale.unlink()
        _download_files(directory)


def _download_files(directory):
    for name, (remote, size, digest) in MODEL_FILES.items():
        destination = directory/name
        if _valid(destination, size, digest):
            continue
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=directory, prefix='sayward-punctuation-', suffix='.part', delete=False) as output:
                temporary = Path(output.name)
                url = f'https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{remote}'
                with urlopen(url, timeout=30) as response:
                    total = 0
                    while chunk := response.read(1024*1024):
                        total += len(chunk)
                        if total > size:
                            raise RuntimeError('Punctuation download exceeds its expected size')
                        output.write(chunk)
            if not _valid(temporary, size, digest):
                raise RuntimeError('Punctuation download failed its integrity check')
            temporary.replace(destination)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


def is_literal(text):
    text = text.strip()
    if not text:
        return False
    if text.startswith(('{', '[')) or '\n' in text or '\r' in text or '`' in text:
        return True
    # Recognizable code/call expressions and commands are literal, not prose.
    if re.fullmatch(r'[\w.$:]+\([^\n]*\)\s*;?', text) or re.fullmatch(r'[A-Za-z]\w*(?:\+\+|#)', text):
        return True
    if re.match(r'^[\w./\\:-]+\s+--?[A-Za-z]', text):
        return True
    if re.fullmatch(r'\w+(?:\s*(?:\+|\*|/|%|==|!=|<=|>=|&&|\|\|)\s*\w+)+', text):
        return True
    if LINK.fullmatch(text):
        return True
    if re.fullmatch(r'[\w.-]+', text) and (not any(c.isalpha() for c in text) or any(c.isdigit() for c in text) or '_' in text or (any(c.isupper() for c in text[1:]) and any(c.islower() for c in text))):
        return True
    if re.fullmatch(r'[\w.-]+\.(?:json|yaml|yml|toml|py|js|ts|sql|csv|txt|md|log|exe|dll|onnx|wav|mp3|html|xml|sh|ps1)', text, re.I):
        return True
    return bool(re.match(r'^[\w.]+\s*(?:=|:=|\+=|-=)\s*\S', text))


def insertion_text(text):
    """History stays clean; every prose paste/copy gets one trailing ASCII space."""
    text = text.strip()
    return text if not text or is_literal(text) else text+' '


def validate_words(original, result):
    def content(value):
        return re.sub(r'[.,!?;:\s-]', '', value).casefold()
    if content(original) != content(result):
        raise RuntimeError('Punctuation processing changed wording; original dictation retained')


class Punctuator:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.session = self.tokenizer = None

    def close(self):
        self.session = self.tokenizer = None

    def _load(self):
        if self.session is not None:
            return
        if not model_ready(self.directory):
            raise RuntimeError('Download the local punctuation model from the tray setup')
        for name, (_, size, digest) in MODEL_FILES.items():
            if not _valid(self.directory/name, size, digest):
                raise RuntimeError('Punctuation model is damaged; download it again from setup')
        import onnxruntime as ort
        from tokenizers import Tokenizer
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.tokenizer = Tokenizer.from_file(str(self.directory/'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=512, stride=128)
        self.session = ort.InferenceSession(str(self.directory/'model.onnx'), sess_options=options, providers=['CPUExecutionProvider'])
        self.labels = json.loads((self.directory/'config.json').read_text())['id2label']

    def _marks(self, text):
        import numpy as np
        self._load()
        encoding = self.tokenizer.encode(text)
        predictions = {}
        for part in [encoding, *encoding.overflowing]:
            ids = np.array([part.ids], dtype=np.int64)
            logits = self.session.run(None, {'input_ids': ids, 'attention_mask': np.ones_like(ids)})[0]
            for index, ((start, end), label) in enumerate(zip(part.offsets, logits.argmax(-1)[0])):
                if end <= start:
                    continue
                context = min(index, len(part.ids)-1-index)
                if end not in predictions or context > predictions[end][0]:
                    predictions[end] = (context, self.labels[str(int(label))])
        return {end: label for end, (_, label) in predictions.items()}

    def restore(self, text):
        text = text.strip()
        if not text or is_literal(text):
            return text
        marks = self._marks(text)
        protected = [(m.start(), m.end()) for m in PROTECTED.finditer(text)]
        pieces, previous, sentence_start = [], 0, True
        for word in WORDS.finditer(text):
            start, end = word.span()
            token = word.group()
            literal = any(a < end and b > start for a, b in protected) or '_' in token or bool(re.search(r'[A-Za-z].*\d|\d.*[A-Za-z]', token))
            existing = token.rstrip(CLOSERS)
            has_mark = bool(existing) and existing[-1] in '.,;:!?…'
            mark = marks.get(end, '0')
            if literal or has_mark or mark not in ('.', ',', '?', ':', '-'):
                mark = ''
            if sentence_start and not literal:
                position = next((i for i, c in enumerate(token) if c.isalpha()), None)
                if position is not None and token[position] in 'abcdefghijklmnopqrstuvwxyz' and not any(c.isupper() for c in token[position+1:]):
                    token = token[:position]+token[position].upper()+token[position+1:]
            pieces.append(text[previous:start]+token+(' -' if mark == '-' else mark))
            previous = end
            sentence_start = bool(mark and mark in TERMINAL) or (not literal and bool(existing) and existing[-1] in TERMINAL)
        result = ''.join(pieces)+text[previous:]
        # Existing source marks are never reinterpreted by the final guard.
        source_tail = text.rstrip(CLOSERS)
        tail = result.rstrip(QUOTES)
        last_word = list(WORDS.finditer(text))[-1]
        protected_end = LINK.fullmatch(last_word.group())
        if not protected_end and not (source_tail and source_tail[-1] in '.,;:!?…'):
            sentence = re.split(r'[.!?](?:[\"\'”’)]*)\s+', result)[-1].strip()
            end_mark = '?' if QUESTION.match(sentence.lstrip('\"\'“‘([')) else '.'
            if tail and tail[-1] not in '.,;:!?…':
                result = result[:len(tail)]+end_mark+result[len(tail):]
        validate_words(text, result)
        return result


if __name__ == '__main__':
    from .core import Config
    from .paths import config_path
    download_model(Config.load(config_path()).punctuation_dir)
    print('Local punctuation model ready (~300 MB). Speech and text stay on this computer.')
