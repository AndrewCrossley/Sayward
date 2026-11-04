import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from dictation import punctuation as p


def renderer(marks=None):
    model=p.Punctuator('/not-loaded')
    model._marks=lambda _:marks or {}
    return model


def test_required_final_marks_and_question_fallback():
    model=renderer()
    assert model.restore('hello world')=='Hello world.'
    assert model.restore('do you understand')=='Do you understand?'
    assert model.restore('Can you open the report?')=='Can you open the report?'
    assert model.restore('Hello, world!')=='Hello, world!'
    assert model.restore('')==''
    assert model.restore('   ')==''
    assert model.restore('What is missing is the report.')=='What is missing is the report.'
    assert model.restore('What is important is safety.')=='What is important is safety.'
    assert model.restore('Please note:')=='Please note:'
    assert model.restore('Warning:')=='Warning:'
    assert model.restore('it worked (after a restart)')=='It worked (after a restart).'
    assert model.restore('please call getValue(A1)')=='Please call getValue(A1).'


def test_sentence_marks_and_casing_preserve_original_words():
    raw='i checked the log it finished successfully can you open the report'
    result=renderer({17:'.',42:'.',66:'?'}).restore(raw)
    assert result=='I checked the log. It finished successfully. Can you open the report?'
    p.validate_words(raw,result)
    with pytest.raises(RuntimeError,match='changed wording'):
        p.validate_words(raw,result.replace('successfully','incorrectly'))


@pytest.mark.parametrize('raw',[
 'https://example.test/report','andrew@example.test','C:\\Projects\\Sayward\\config.json',
 '/home/andrew/config.json','config.json','example_value','fooBar','A1','3.14',
 '{"sensor":"A1","value":3.14}','[1,2,3]','value = 3.14','`getValue(A1)`',
 'foo()','getValue(A1)','C++','C#','python -m pytest tests','git --version','a + b',
])
def test_literals_are_unchanged_without_loading_a_model(raw):
    model=p.Punctuator('/missing')
    assert model.restore(raw)==raw
    assert p.insertion_text(raw)==raw


def test_numbers_identifiers_paths_and_existing_marks_are_preserved():
    raw='the measurement is 3.14 on channel A1'
    assert renderer({21:'.',37:'.'}).restore(raw)=='The measurement is 3.14 on channel A1.'
    raw='please open https://example.test/report'
    assert renderer({len(raw):'.'}).restore(raw)=='Please open https://example.test/report'
    assert renderer({5:'.',13:'?'}).restore('Hello, world!')=='Hello, world!'


def test_copy_and_repeated_insertion_have_clean_history_and_one_separator():
    first='Hello.';second='How are you?'
    assert p.insertion_text(first)+p.insertion_text(second)=='Hello. How are you? '
    assert p.insertion_text(p.insertion_text(first))=='Hello. '
    assert first=='Hello.' and p.insertion_text('')==''
    assert '\n' not in p.insertion_text(first)


def test_download_validates_and_atomically_installs_without_partial_cache(monkeypatch,tmp_path):
    payload=b'public model fixture';digest=hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(p,'MODEL_FILES',{'model.onnx':('model.onnx',len(payload),digest)})
    monkeypatch.setattr(p,'urlopen',lambda *args,**kwargs:io.BytesIO(payload))
    p.download_model(tmp_path)
    assert (tmp_path/'model.onnx').read_bytes()==payload
    assert not list(tmp_path.glob('*.part'))
    monkeypatch.setattr(p,'urlopen',lambda *_args,**_kwargs:pytest.fail('valid cache needs no network'))
    p.download_model(tmp_path)


def test_download_lock_protects_active_partial_and_reclaims_interrupted_setup(monkeypatch,tmp_path):
    payload=b'public fixture'
    monkeypatch.setattr(p,'MODEL_FILES',{'model.onnx':('model.onnx',len(payload),hashlib.sha256(payload).hexdigest())})
    monkeypatch.setattr(p,'urlopen',lambda *args,**kwargs:io.BytesIO(payload))
    partial=tmp_path/'sayward-punctuation-interrupted.part';partial.write_bytes(b'partial')
    with p._download_lock(tmp_path):
        with pytest.raises(RuntimeError,match='already in progress'):
            p.download_model(tmp_path)
        assert partial.exists()
    p.download_model(tmp_path)
    assert not partial.exists() and (tmp_path/'model.onnx').read_bytes()==payload


def test_failed_download_retains_previous_file_and_removes_partial(monkeypatch,tmp_path):
    payload=b'correct data'
    monkeypatch.setattr(p,'MODEL_FILES',{'model.onnx':('model.onnx',len(payload),hashlib.sha256(payload).hexdigest())})
    (tmp_path/'model.onnx').write_bytes(b'old incomplete file')
    monkeypatch.setattr(p,'urlopen',lambda *args,**kwargs:io.BytesIO(b'bad'))
    with pytest.raises(RuntimeError,match='integrity'):
        p.download_model(tmp_path)
    assert (tmp_path/'model.onnx').read_bytes()==b'old incomplete file'
    assert not list(tmp_path.glob('*.part'))


@pytest.mark.skipif(not os.environ.get('SAYWARD_PUNCTUATION_MODEL'),reason='Pinned public model integration; opt in with local weights')
def test_real_offline_model_preserves_words_and_restores_reviewed_corpus(monkeypatch):
    def no_network(*args,**kwargs):pytest.fail('Runtime inference must stay offline')
    monkeypatch.setattr(p,'urlopen',no_network)
    model=p.Punctuator(os.environ['SAYWARD_PUNCTUATION_MODEL'])
    corpus=[
      ('i checked the log it finished successfully can you open the report','I checked the log. It finished successfully. Can you open the report?'),
      ('the measurement is 3.14 on channel A1','The measurement is 3.14 on channel A1.'),
      ('Can you open the report?','Can you open the report?'),
      ('i do not want my words rewritten i want periods and question marks do you understand','I do not want my words rewritten. I want periods and question marks. Do you understand?'),
    ]
    for raw,expected in corpus:
        actual=model.restore(raw)
        assert actual==expected
        p.validate_words(raw,actual)
    long_text=((' '.join(raw for raw,_ in corpus)+' ')*12).strip()
    actual=model.restore(long_text)
    p.validate_words(long_text,actual)
    assert actual[-1] in '.?!'
    model.close()
    assert model.session is None and model.tokenizer is None
