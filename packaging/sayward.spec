from PyInstaller.utils.hooks import collect_all, copy_metadata
from pathlib import Path

root=Path(SPECPATH).parent
datas=[(str(root/'sounds'),'sounds'),(str(root/'packaging/THIRD-PARTY-NOTICES.md'),'.')]
binaries=[]
hidden=['dictation.windows_app','dictation.worker','pystray._win32']
for package in ('faster_whisper','ctranslate2','av','onnxruntime','tokenizers','sounddevice','huggingface_hub','certifi'):
    data,binary,imports=collect_all(package)
    datas+=data;binaries+=binary;hidden+=imports
for package in ('faster-whisper','ctranslate2','huggingface-hub','av','numpy','onnxruntime','sounddevice','pystray','pillow','tokenizers','cffi','certifi'):
    datas+=copy_metadata(package)
a=Analysis([str(root/'windows_entry.py')],pathex=[str(root)],datas=datas,binaries=binaries,hiddenimports=hidden,excludes=['gi','Xlib','pytest','IPython'])
pyz=PYZ(a.pure)
gui=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Sayward',console=False,icon=str(root/'packaging/sayward.ico'))
worker=EXE(pyz,a.scripts,[],exclude_binaries=True,name='SaywardWorker',console=True,icon=str(root/'packaging/sayward.ico'))
coll=COLLECT(gui,worker,a.binaries,a.datas,name='Sayward')
