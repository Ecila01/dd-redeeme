; Inno Setup 6 script - DD RedeeMe (兑了么) installer
; Build the portable exe first (DDRedeeMe.spec -> dist/DD RedeeMe.exe),
; then compile this script with ISCC.
; Output: <workspace>/release/v{version}/DD RedeeMe_{version}_x64-setup.exe
; NOTE: keep all literal strings ASCII (the .iss is saved without BOM).

#define MyAppVersion "0.1.0"
#define MyAppName "DD RedeeMe"
#define MyAppExeName "DD RedeeMe.exe"

[Setup]
AppId={{7A6C2E10-3D9E-4E11-B5C8-EC1A01DD9A01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
; Per-user install dir (writable, no admin): config.json lives next to the exe
DefaultDirName={localappdata}\Programs\DDRedeeMe
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=..\..\release\v{#MyAppVersion}
OutputBaseFileName=DD RedeeMe_{#MyAppVersion}_x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional tasks:"
Name: "autostart"; Description: "Start automatically at Windows login (current user)"; GroupDescription: "Additional tasks:"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Ship default config, never overwrite user edits, keep it after uninstall
Source: "..\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall

[Icons]
; AppUserModelID links the shortcuts to our toast identity (Ecila01.DDRedeeMe)
; so Windows notifications group correctly for the INSTALLED app.
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppName} - game redeem codes widget"; AppUserModelID: "Ecila01.DDRedeeMe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; AppUserModelID: "Ecila01.DDRedeeMe"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DDRedeeMe"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Nothing to clean in %APPDATA%\DDRedeeMe - user cache/marks are kept on purpose.
