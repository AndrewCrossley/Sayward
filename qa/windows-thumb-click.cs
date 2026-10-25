// Simulates only the ordinary Back/Forward mouse events in a disposable VM.
using System;
using System.Runtime.InteropServices;
internal static class SaywardThumbFixture {
    [StructLayout(LayoutKind.Sequential)] private struct Mouse { public int x,y; public uint data,flags,time; public UIntPtr extra; }
    [StructLayout(LayoutKind.Explicit)] private struct Value { [FieldOffset(0)] public Mouse mouse; }
    [StructLayout(LayoutKind.Sequential)] private struct Input { public uint type; public Value value; }
    [DllImport("user32.dll")] private static extern uint SendInput(uint count,Input[] input,int size);
    [STAThread] private static void Main(string[] args) {
        uint button=uint.Parse(args[0]); if(button!=1 && button!=2) throw new ArgumentException();
        Input[] events={new Input{value=new Value{mouse=new Mouse{data=button,flags=0x80}}},new Input{value=new Value{mouse=new Mouse{data=button,flags=0x100}}}};
        if(SendInput(2,events,Marshal.SizeOf(typeof(Input)))!=2) throw new InvalidOperationException("Input blocked");
    }
}
