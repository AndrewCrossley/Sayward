"""Win32 desktop boundary with guarded paste and explicit opt-in Enter."""
import ctypes as C
from ctypes import wintypes as W
import queue
import threading
import time

U = C.WinDLL('user32', use_last_error=True)
K = C.WinDLL('kernel32', use_last_error=True)
PTR = C.c_size_t
RESULT = C.c_ssize_t


class Point(C.Structure):
    _fields_ = [('x', W.LONG), ('y', W.LONG)]


class MouseEvent(C.Structure):
    _fields_ = [('pt', Point), ('mouseData', W.DWORD), ('flags', W.DWORD),
                ('time', W.DWORD), ('extra', PTR)]


class GUIInfo(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD),
                *[(name, W.HWND) for name in ('active','focus','capture','menu','move','caret')],
                ('rect', W.RECT)]


class KeyboardInput(C.Structure):
    _fields_ = [('vk', W.WORD), ('scan', W.WORD), ('flags', W.DWORD),
                ('time', W.DWORD), ('extra', PTR)]


class MouseInput(C.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('data', W.DWORD),
                ('flags', W.DWORD), ('time', W.DWORD), ('extra', PTR)]


class InputUnion(C.Union):
    _fields_ = [('ki', KeyboardInput), ('mi', MouseInput)]


class Input(C.Structure):
    _fields_ = [('type', W.DWORD), ('value', InputUnion)]


HOOK = C.WINFUNCTYPE(RESULT, C.c_int, PTR, RESULT)
U.SetWindowsHookExW.argtypes = [C.c_int, HOOK, W.HINSTANCE, W.DWORD]
U.SetWindowsHookExW.restype = W.HANDLE
U.CallNextHookEx.argtypes = [W.HANDLE, C.c_int, PTR, RESULT]
U.CallNextHookEx.restype = RESULT
U.UnhookWindowsHookEx.argtypes = [W.HANDLE]
U.GetForegroundWindow.restype = W.HWND
U.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
U.GetGUIThreadInfo.argtypes = [W.DWORD, C.POINTER(GUIInfo)]
U.SendInput.argtypes = [W.UINT, C.POINTER(Input), C.c_int]
U.PostThreadMessageW.argtypes = [W.DWORD, W.UINT, PTR, RESULT]
U.OpenClipboard.argtypes = [W.HWND]
U.CreateWindowExW.argtypes = [W.DWORD,W.LPCWSTR,W.LPCWSTR,W.DWORD,C.c_int,C.c_int,C.c_int,C.c_int,W.HWND,W.HMENU,W.HINSTANCE,C.c_void_p]
U.CreateWindowExW.restype = W.HWND
U.DestroyWindow.argtypes = [W.HWND]
U.SetClipboardData.argtypes = [W.UINT, W.HANDLE]
U.SetClipboardData.restype = W.HANDLE
K.GetModuleHandleW.argtypes = [W.LPCWSTR]
K.GetModuleHandleW.restype = W.HMODULE
K.GlobalAlloc.argtypes = [W.UINT, C.c_size_t]
K.GlobalAlloc.restype = W.HGLOBAL
K.GlobalLock.argtypes = [W.HGLOBAL]
K.GlobalLock.restype = C.c_void_p
K.GlobalUnlock.argtypes = [W.HGLOBAL]
K.GlobalFree.argtypes = [W.HGLOBAL]
K.CloseHandle.argtypes = [W.HANDLE]
K.CreateMutexW.argtypes = [C.c_void_p, W.BOOL, W.LPCWSTR]
K.CreateMutexW.restype = W.HANDLE
K.CreateJobObjectW.argtypes = [C.c_void_p, W.LPCWSTR]
K.CreateJobObjectW.restype = W.HANDLE
K.SetInformationJobObject.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
K.AssignProcessToJobObject.argtypes = [W.HANDLE, W.HANDLE]
K.GetTickCount64.restype = C.c_ulonglong


class Singleton:
    def __init__(self):
        self.handle = K.CreateMutexW(None, False, 'Local\\Sayward.Dictation')
        if not self.handle:
            raise C.WinError(C.get_last_error())
        if C.get_last_error() == 183:
            self.close()
            raise RuntimeError('Sayward is already running. Open its microphone tray menu.')

    def close(self):
        if self.handle:
            K.CloseHandle(self.handle)
            self.handle = None


class JobLimits(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64),
                ('flags', W.DWORD), ('minimum', C.c_size_t), ('maximum', C.c_size_t),
                ('active_limit', W.DWORD), ('affinity', PTR),
                ('priority', W.DWORD), ('scheduling', W.DWORD)]


class IOCounters(C.Structure):
    _fields_ = [(name,C.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]


class JobInfo(C.Structure):
    _fields_ = [('limits',JobLimits),('io',IOCounters),
                *[(name,C.c_size_t) for name in ('process_memory','job_memory','peak_process','peak_job')]]


class WorkerJob:
    def __init__(self, process):
        self.handle = K.CreateJobObjectW(None, None)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        info = JobInfo()
        info.limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not K.SetInformationJobObject(self.handle, 9, C.byref(info), C.sizeof(info)) or not K.AssignProcessToJobObject(self.handle, W.HANDLE(int(process._handle))):
            error = C.get_last_error()
            self.close()
            raise C.WinError(error)

    def close(self):
        if self.handle:
            K.CloseHandle(self.handle)
            self.handle = None


class Desktop:
    def __init__(self, button, paste_button=9):
        if {button,paste_button} != {8,9}:
            raise ValueError('Windows supports Back/Forward thumb buttons 8 and 9; assign one to record and one to paste.')
        self.buttons = (button,paste_button)
        self.clipboard_window = U.CreateWindowExW(0,'STATIC','Sayward Clipboard',0,0,0,0,0,W.HWND(-3),None,K.GetModuleHandleW(None),None)
        if not self.clipboard_window:
            raise C.WinError(C.get_last_error())
        self.queue = queue.Queue()
        self.ready = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        if not self.ready.wait(5) or self.error:
            self.close()
            raise RuntimeError(self.error or 'Windows mouse hook did not start.')

    def _listen(self):
        self.thread_id = K.GetCurrentThreadId()
        msg = W.MSG()
        U.PeekMessageW(C.byref(msg), None, 0, 0, 0)
        @HOOK
        def callback(code, event, data):
            if code >= 0 and event in (0x020B,0x020C):
                mouse = C.cast(data, C.POINTER(MouseEvent)).contents
                extra = mouse.mouseData >> 16
                button = {1:8,2:9}.get(extra)
                if button in self.buttons:
                    if event == 0x020B:
                        age = ((K.GetTickCount64() & 0xffffffff) - mouse.time) & 0xffffffff
                        self.queue.put((button, time.monotonic() - age / 1000))
                    return 1
            return U.CallNextHookEx(None, code, event, data)
        self.callback = callback
        hook = U.SetWindowsHookExW(14, callback, K.GetModuleHandleW(None), 0)
        if not hook:
            self.error = str(C.WinError(C.get_last_error()))
        self.ready.set()
        if hook:
            try:
                while U.GetMessageW(C.byref(msg),None,0,0) > 0:
                    U.TranslateMessage(C.byref(msg))
                    U.DispatchMessageW(C.byref(msg))
            finally:
                U.UnhookWindowsHookEx(hook)

    def events(self):
        events = []
        while True:
            try:
                events.append(self.queue.get_nowait())
            except queue.Empty:
                return events

    def focus(self):
        window = U.GetForegroundWindow()
        if not window:
            return None
        thread = U.GetWindowThreadProcessId(window, None)
        info = GUIInfo(cbSize=C.sizeof(GUIInfo))
        return (window, info.focus if U.GetGUIThreadInfo(thread,C.byref(info)) else 0)

    def copy(self, text):
        if '\x00' in text:
            raise ValueError('The transcript contains an unsupported null character.')
        raw = (text+'\0').encode('utf-16-le')
        if not U.OpenClipboard(self.clipboard_window):
            raise RuntimeError('Clipboard is busy. Focus your field and press Forward to retry.')
        memory = None
        try:
            if not U.EmptyClipboard():
                raise C.WinError(C.get_last_error())
            memory = K.GlobalAlloc(0x0002, len(raw))
            address = K.GlobalLock(memory) if memory else None
            if not address:
                raise C.WinError(C.get_last_error())
            C.memmove(address, raw, len(raw))
            K.GlobalUnlock(memory)
            if not U.SetClipboardData(13, memory):
                raise C.WinError(C.get_last_error())
            memory = None  # Windows owns the allocation now.
        finally:
            if memory:
                K.GlobalFree(memory)
            U.CloseClipboard()

    def paste(self, text, target):
        if not target or self.focus() != target:
            raise RuntimeError('Focus changed. Focus a text field and press Forward to recover the transcript.')
        if any(U.GetAsyncKeyState(key) & 0x8000 for key in (0x10,0x11,0x12,0x5B,0x5C)):
            raise RuntimeError('Release keyboard modifiers, then press Forward to paste.')
        self.copy(text)
        if self.focus() != target:
            raise RuntimeError('Focus changed. Press Forward in the intended field to recover.')
        def key(vk,up=False):
            return Input(type=1,value=InputUnion(ki=KeyboardInput(vk=vk,flags=2 if up else 0)))
        events=(Input*4)(key(0x11),key(0x56),key(0x56,True),key(0x11,True))
        if U.SendInput(4,events,C.sizeof(Input)) != 4:
            release=(Input*2)(key(0x56,True),key(0x11,True))
            U.SendInput(2,release,C.sizeof(Input))
            raise RuntimeError('Windows blocked insertion. Copy the selected transcript from the tray. Elevated/secure fields are unsupported.')

    def close(self):
        if getattr(self,'thread_id',None):
            U.PostThreadMessageW(self.thread_id,0x0012,0,0)
            self.thread.join(timeout=2)
        if getattr(self,'clipboard_window',None):
            U.DestroyWindow(self.clipboard_window)
            self.clipboard_window = None

    def enter(self, target):
        if not target or self.focus() != target:
            raise RuntimeError('Focus changed; Enter cancelled.')
        if any(U.GetAsyncKeyState(key) & 0x8000 for key in (0x10,0x11,0x12,0x5B,0x5C)):
            raise RuntimeError('Keyboard modifiers are held; Enter cancelled.')
        events=(Input*2)(Input(type=1,value=InputUnion(ki=KeyboardInput(vk=0x0D))),
                         Input(type=1,value=InputUnion(ki=KeyboardInput(vk=0x0D,flags=2))))
        if self.focus() != target:
            raise RuntimeError('Focus changed; Enter cancelled.')
        if U.SendInput(2,events,C.sizeof(Input)) != 2:
            release=(Input*1)(events[1])
            U.SendInput(1,release,C.sizeof(Input))
            raise RuntimeError('Windows blocked Enter; submit manually.')
