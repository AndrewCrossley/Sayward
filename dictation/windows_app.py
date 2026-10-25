"""Windows tray and revisitable setup/practice UI; inference stays off the UI thread."""
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .core import Config
from .paths import config_path, assets
from .session import Session
from .windows_native import Desktop, Singleton, U


def model_ready(config):
    def complete(path):
        return all((path/name).is_file() for name in ('model.bin','config.json','tokenizer.json')) and any((path/name).is_file() for name in ('vocabulary.txt','vocabulary.json'))
    if Path(config.model).is_dir():
        return complete(Path(config.model))
    try:
        from huggingface_hub import snapshot_download
        path=Path(snapshot_download('Systran/faster-whisper-'+config.model,cache_dir=config.cache_dir,local_files_only=True))
        return complete(path)
    except Exception:
        return False


class WindowsApp(Session):
    def __init__(self, config):
        self.lock=Singleton()
        self.root=tk.Tk()
        self.root.withdraw()
        self.root.title('Sayward')
        self.callbacks=queue.Queue()
        try:
            desktop=Desktop(config.button, config.paste_button)
        except Exception:
            self.lock.close()
            self.root.destroy()
            raise
        super().__init__(config, desktop, self.dispatch)
        self.guide=None
        self.history_window=None
        self.setup_window=None
        self.downloading=False
        self.status='Ready — Back thumb button to record'
        self.tray_frame=None
        self.ready_model=model_ready(config)
        self._make_tray()
        self.root.after(20,self.pump)
        self.root.after(100,self.meter)
        self.root.after(1000,self.timer)
        if not self.ready_model:
            self.setup()

    def dispatch(self, callback, *args):
        self.callbacks.put((callback,args))

    def pump(self):
        if self.closed:
            return
        while True:
            try:callback,args=self.callbacks.get_nowait()
            except queue.Empty:break
            callback(*args)
            if self.closed:return
        self.poll()
        self.root.after(20,self.pump)

    def timer(self):
        if not self.closed:
            self.tick()
            self.root.after(1000,self.timer)

    @staticmethod
    def image(state, frame=0):
        from PIL import Image, ImageDraw
        image=Image.new('RGBA',(64,64),(0,0,0,0));draw=ImageDraw.Draw(image)
        color={'idle':(115,125,140),'working':(245,175,35),'error':(230,70,70)}.get(state,(100+int(frame*14),25,35))
        if state=='recording':
            draw.ellipse((2,2,62,62),fill=(*color,40+frame*10))
        draw.rounded_rectangle((24,10,40,37),radius=8,fill=color)
        draw.arc((18,17,46,45),0,180,fill=color,width=4)
        draw.line((32,45,32,54),fill=color,width=4)
        draw.line((24,55,40,55),fill=color,width=4)
        if state=='recording':
            for i in range(5):
                draw.rectangle((5+i*11,59,12+i*11,63),fill=color if i<=frame//3 else (50,50,50))
        return image

    def _make_tray(self):
        import pystray
        Item=pystray.MenuItem
        def action(callback):
            return lambda *_: self.dispatch(callback)
        self.tray=pystray.Icon('Sayward',self.image('idle'),'Sayward — Ready',pystray.Menu(
            Item(lambda _:self.status,lambda *_:None,enabled=False),
            Item(lambda _:'Stop and transcribe' if self.state=='recording' else 'Start recording',action(self.toggle),enabled=lambda _:self.state!='working'),
            Item('Cancel recording',action(self.cancel),enabled=lambda _:self.state=='recording'),
            Item('Paste selected transcript (Forward)',action(self.paste_last),enabled=lambda _:bool(self.history.text) and self.state not in ('working','recording')),
            Item('Recent transcripts (last 5)',action(self.open_history)),
            Item('Copy selected transcript',action(self.copy_last)),
            Item('How to use / Practice',action(self.help),default=True),
            Item('Model setup',action(self.setup)),
            Item('Sound cues',action(self.toggle_sound),checked=lambda _:self.config.sound),
            Item('Unload model',action(self.unload),enabled=lambda _:self.state not in ('working','recording')),
            Item('Quit',action(self.quit)),
        ))
        self.tray.run_detached()

    def set_state(self,state,message):
        if self.closed:return False
        self.state,self.status=state,message
        if state=='recording':self.recording_message=message
        self.tray.icon=self.image(state)
        self.tray.title=('Sayward — '+message)[:127]
        self.tray.update_menu()
        if self.guide and self.guide.winfo_exists():
            self.practice_status.set(message)
            self.practice_button.config(text='Stop and transcribe' if state=='recording' else 'Start recording',state='disabled' if state=='working' else 'normal')
        return False

    def toggle(self):
        if self.downloading:
            self.set_state('idle','Model download in progress — open Model setup')
            return
        if not self.ready_model:
            self.setup()
            return
        super().toggle()

    def cue(self,event):
        if self.config.sound:
            import winsound
            try:winsound.PlaySound(str(assets()/'sounds'/f'{event}.wav'),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            except RuntimeError:pass

    def toggle_sound(self):
        self.config.sound=not self.config.sound
        self.save()

    def meter(self):
        if self.closed:return
        if self.state=='recording':
            now=time.monotonic()
            raw=self.recorder.level if now-self.recorder.level_updated_at<0.4 else 0
            self.meter_level=max(raw,self.meter_level*0.72)
            frame=min(11,round(self.meter_level*11))
            message='Recording — no mic input; check mute' if now-self.recorder.last_signal>=2 else self.recording_message
            if (frame,message)!=self.tray_frame:
                self.tray.icon=self.image('recording',frame)
                self.tray.title=('Sayward — '+message)[:127]
                self.status=message
                self.tray_frame=(frame,message)
                if self.guide and self.guide.winfo_exists():self.practice_status.set(message)
        else:
            self.meter_level=0;self.tray_frame=None
        self.root.after(100,self.meter)

    def window(self,title,width=650,height=510):
        window=tk.Toplevel(self.root)
        window.title('Sayward — '+title)
        window.geometry(f'{width}x{height}')
        window.minsize(500,360)
        window.lift()
        window.after(50,window.focus_force)
        return window

    def help(self):
        if self.guide and self.guide.winfo_exists():
            self.guide.deiconify();self.guide.lift();self.guide.focus_force();return
        self.guide=self.window('How to use / Practice',660,540)
        box=ttk.Frame(self.guide,padding=16);box.pack(fill='both',expand=True)
        instructions=('1. Focus a text field. Click Back thumb to record, speak, then click Back to stop.\n'
            '2. The red microphone glows with input; dim + check mute means little/no audio.\n'
            '3. Amber means transcribing. Keep the destination focused until text arrives.\n'
            '4. Forward thumb pastes the selected result again. It never presses Enter.\n'
            '5. Tray → Recent transcripts keeps your last five results for this session.\n\n'
            'Practice below. The green Start/Stop button does the same job as Back.\n'
            'Close this guide any time; reopen it through the tray. Dictation replaces the clipboard.\n'
            'Audio/transcription stay local. Model setup downloads weights once.\n'
            'Elevated/secure fields are unsupported; use ordinary applications.')
        ttk.Label(box,text=instructions,wraplength=610,justify='left').pack(fill='x',pady=(0,12))
        self.practice_entry=ttk.Entry(box)
        self.practice_entry.pack(fill='x',pady=8)
        self.practice_entry.focus_set()
        style=ttk.Style();style.configure('Practice.TButton',foreground='#006025')
        self.practice_button=tk.Button(box,text='Start recording',background='#187944',foreground='white',takefocus=False,command=self.practice_toggle)
        self.practice_button.pack(fill='x',pady=8)
        self.practice_status=tk.StringVar(value=self.status)
        ttk.Label(box,textvariable=self.practice_status,wraplength=600).pack(fill='x',pady=8)
        ttk.Button(box,text='Close guide',command=self.guide.destroy).pack(side='bottom',fill='x')
        self.guide.bind('<Alt-r>',lambda _:self.practice_toggle())

    def practice_toggle(self):
        self.practice_entry.focus_set()
        self.toggle()

    def open_history(self):
        if self.history_window and self.history_window.winfo_exists():
            self.history_window.deiconify();self.history_window.lift();self.history_window.focus_force();return
        self.history_window=self.window('Recent transcripts',680,500)
        box=ttk.Frame(self.history_window,padding=14);box.pack(fill='both',expand=True)
        ttk.Label(box,text='Select a result, close history, focus your destination and press Forward.\nNewest is selected after each successful recording. History clears on Quit.',wraplength=630).pack(fill='x')
        self.history_list=tk.Listbox(box,height=5,exportselection=False)
        self.history_list.pack(fill='x',pady=10)
        self.history_list.bind('<<ListboxSelect>>',self.select_history)
        preview_box=ttk.Frame(box);preview_box.pack(fill='both',expand=True)
        scroll=ttk.Scrollbar(preview_box);scroll.pack(side='right',fill='y')
        self.preview=tk.Text(preview_box,height=6,wrap='word',state='disabled',yscrollcommand=scroll.set)
        self.preview.pack(fill='both',expand=True);scroll.config(command=self.preview.yview)
        ttk.Button(box,text='Close history',command=self.history_window.destroy).pack(fill='x',pady=(12,0))
        self.refresh_history()

    def refresh_history(self):
        if not self.history_window or not self.history_window.winfo_exists():return
        self.history_list.delete(0,'end')
        for text in self.history.items:self.history_list.insert('end',' '.join(text.split())[:95])
        if self.history.items:self.history_list.selection_set(self.history.selected)
        self.show_preview()

    def select_history(self,_=None):
        selection=self.history_list.curselection()
        if selection:self.history.select(selection[0]);self.show_preview()

    def show_preview(self):
        self.preview.config(state='normal');self.preview.delete('1.0','end')
        self.preview.insert('1.0',self.history.text or 'No transcripts yet. Record speech with Back.')
        self.preview.config(state='disabled')

    def copy_last(self):
        if self.history.text:
            try:self.desktop.copy(self.history.text);self.set_state(self.state,'Selected transcript copied')
            except Exception as exc:self.set_state('error',str(exc))

    def save(self):
        path=config_path();path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(self.config.__dict__,indent=2)+'\n',encoding='utf-8')

    def setup(self):
        if self.setup_window and self.setup_window.winfo_exists():
            self.setup_window.deiconify();self.setup_window.lift();return
        self.setup_window=self.window('Model setup',650,420)
        box=ttk.Frame(self.setup_window,padding=18);box.pack(fill='both',expand=True)
        ttk.Label(box,text='Choose your local speech model',font=('Segoe UI',14,'bold')).pack(anchor='w')
        ttk.Label(box,text='Medium is the original quality setting (~1.5 GB download). Small uses less disk and is faster on CPU.\nInternet is needed only to download model files from Hugging Face. Your audio is never uploaded.\nCompatible NVIDIA CUDA 12/cuDNN 9 is used when available; otherwise CPU is automatic.',wraplength=600).pack(fill='x',pady=14)
        self.model_choice=ttk.Combobox(box,values=('medium','small','base','tiny'),state='readonly')
        self.model_choice.set(self.config.model if self.config.model in ('medium','small','base','tiny') else 'medium')
        self.model_choice.pack(fill='x')
        self.setup_status=tk.StringVar(value='Downloading model files. Keep Sayward open.' if self.downloading else 'Ready to download, or choose an existing model folder.')
        ttk.Label(box,textvariable=self.setup_status,wraplength=600).pack(fill='x',pady=12)
        self.download_progress=ttk.Progressbar(box,mode='indeterminate')
        self.download_progress.pack(fill='x',pady=4)
        if self.downloading:self.download_progress.start()
        self.download_button=ttk.Button(box,text='Download selected model',command=self.download)
        self.download_button.pack(fill='x',pady=5)
        self.choose_button=ttk.Button(box,text='Use existing model folder',command=self.choose_model)
        self.choose_button.pack(fill='x',pady=5)
        ttk.Button(box,text='Close setup',command=self.setup_window.destroy).pack(side='bottom',fill='x')
        if self.downloading:self.download_button.config(state='disabled');self.choose_button.config(state='disabled')

    def choose_model(self):
        if self.state in ('recording','working') or self.downloading:return
        folder=filedialog.askdirectory(parent=self.setup_window,title='Choose faster-whisper model folder')
        if not folder:return
        old=self.config.model;self.config.model=folder
        if not model_ready(self.config):
            self.config.model=old;self.setup_status.set('Folder needs model.bin, config.json, tokenizer.json and vocabulary.txt/json.');return
        self.ready_model=True;self.save();self.unload();self.setup_status.set('Model ready. Close setup and use Back to record.')

    def download(self):
        if self.downloading or self.state in ('recording','working'):return
        self.downloading=True
        choice=self.model_choice.get()
        self.setup_status.set('Downloading '+choice+'… Keep Sayward open. You can close this window and reopen Model setup.')
        self.download_progress.start()
        self.download_button.config(state='disabled');self.choose_button.config(state='disabled')
        def run():
            try:
                from huggingface_hub import snapshot_download
                snapshot_download('Systran/faster-whisper-'+choice,cache_dir=self.config.cache_dir,
                    allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*'])
                error=None
            except Exception as exc:error=str(exc)
            self.dispatch(self.download_finished,choice,error)
        threading.Thread(target=run,daemon=True).start()

    def download_finished(self,choice,error):
        self.downloading=False
        if not error:
            self.config.model=choice;self.ready_model=model_ready(self.config);self.save();self.unload()
        if self.setup_window and self.setup_window.winfo_exists():
            self.download_progress.stop()
            self.download_button.config(state='normal');self.choose_button.config(state='normal')
            self.setup_status.set(('Download failed: '+error) if error else 'Model ready. Close setup and use Back to record.')
        self.set_state('error' if error else 'idle','Model download failed — open Model setup' if error else 'Model ready — Back thumb button to record')

    def quit(self):
        if self.closed:return
        self.shutdown()
        self.tray.stop()
        self.lock.close()
        self.root.destroy()


def main():
    try:
        U.SetProcessDPIAware()
        app=WindowsApp(Config.load(config_path()))
        app.root.mainloop()
    except Exception as exc:
        U.MessageBoxW(None,str(exc),'Sayward',0x10)
