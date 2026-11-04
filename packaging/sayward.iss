#define AppVersion "0.3.0"
[Setup]
AppId={{07DE0649-760D-42E8-AEBF-302903F52472}
AppName=Sayward
AppVersion={#AppVersion}
AppPublisher=Andrew Crossley
AppPublisherURL=https://github.com/AndrewCrossley/Sayward
DefaultDirName={localappdata}\Programs\Sayward
DefaultGroupName=Sayward
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=Sayward-Setup-{#AppVersion}-x64
SetupIconFile=sayward.ico
UninstallDisplayIcon={app}\Sayward.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AppMutex=Sayward.Dictation

[Tasks]
Name: startup; Description: "Start Sayward when I sign in"; Flags: unchecked
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Sayward\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Sayward"; Filename: "{app}\Sayward.exe"
Name: "{group}\Uninstall Sayward"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Sayward"; Filename: "{app}\Sayward.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: Sayward; ValueData: """{app}\Sayward.exe"""; Tasks: startup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Sayward.exe"; Description: "Launch Sayward"; Flags: nowait postinstall skipifsilent runasoriginaluser

; Models/config are outside the install directory and deliberately retained.
