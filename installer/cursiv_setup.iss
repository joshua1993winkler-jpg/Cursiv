; ============================================================
; Cursiv v3.14-U09 — Auto-detect terminal launch, no flag needed
; Produces: installer\Output\Cursiv-Setup-3.14-U09.exe
;
; Offline-first AI workspace. Runs without internet after install.
; Ollama + llama3.1 downloaded post-install (~4.7 GB, one time).
;
; Compile: iscc installer\cursiv_setup.iss
;          (or run scripts\package.bat)
; ============================================================

#define AppName      "Cursiv"
#define AppVer       "3.14-U09"
#define AppPublisher "Joshua Winkler"
#define AppURL       "https://github.com/joshua1993winkler-jpg/Cursiv"
#define AppExe       "Cursiv.exe"
#define AppID        "{{A7B1C2D3-E4F5-4A6B-9C7D-8E0F1A2B3C4D}}"

[Setup]
AppId={#AppID}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE
InfoAfterFile=..\CHANGELOG.md
AppComments=Offline AI workspace with cascade routing (xAI → OpenAI → Claude → Ollama), live status indicators, and security-question password recovery. No internet required after install. Your data never leaves your machine.
OutputDir=Output
OutputBaseFilename=Cursiv-Setup-3.14-U09
SetupIconFile=..\launcher\resources\icons\cursiv.ico
WizardSmallImageFile=..\launcher\resources\icons\cursiv_256.png
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}";                                                       GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart";    Description: "Start Cursiv when Windows starts";                                             GroupDescription: "Startup:"; Flags: unchecked
Name: "csb";          Description: "Cursiv Substrate Browser — adds a desktop icon for the local curs.http:// browser"; GroupDescription: "Optional components:"

[Files]
; Main application (one-dir PyInstaller bundle)
Source: "..\dist\Cursiv\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Ollama bootstrap — downloads and installs Ollama + llama3.1 post-install
Source: "..\scripts\install_ollama.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}";  Filename: "{uninstallexe}"

; Desktop shortcut — main launcher (optional)
Name: "{autodesktop}\{#AppName}";                  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

; Desktop shortcut — Cursiv Substrate Browser (optional CSB task)
Name: "{autodesktop}\Cursiv Substrate Browser";    Filename: "cmd.exe"; \
  Parameters: "/c ""{app}\{#AppExe}"" --browser & pause"; \
  IconFilename: "{app}\{#AppExe}"; \
  Comment: "Open the Cursiv substrate layer browser (curs.http://)"; \
  Tasks: csb

[Registry]
; Autostart (optional task) — HKCU so no admin needed
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExe}"" --tray"; \
  Flags: uninsdeletevalue; Tasks: autostart

; Add install dir to user PATH so 'cursiv' works from any terminal
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); \
  Flags: preservestringtype uninsdeletevalue

[Run]
; AI engine bootstrap — downloads Ollama (latest) and pulls llama3.1 (~4.7 GB) in a visible window
; Runs non-blocking so the installer finishes immediately; user can minimise and wait
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Normal -File ""{app}\scripts\install_ollama.ps1"""; \
  Description: "Set up local AI engine (Ollama + llama3.1 model — ~4.7 GB download)"; \
  Flags: nowait postinstall skipifsilent runascurrentuser

; CSB: install PyQt6-WebEngine when the substrate browser task is selected
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Normal -Command ""pip install PyQt6-WebEngine>=6.7.0"""; \
  Description: "Install Cursiv Substrate Browser engine (~80 MB)"; \
  Flags: nowait postinstall skipifsilent runascurrentuser; Tasks: csb

; Launch after install
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill running instance before uninstall
Filename: "taskkill"; Parameters: "/f /im {#AppExe}"; \
  Flags: runhidden; RunOnceId: "KillCursiv"

[Code]
// Returns true if Param is not already in the user PATH
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Lowercase(Param) + ';', ';' + Lowercase(OrigPath) + ';') = 0;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  // PATH is registered; new terminals will pick it up automatically
end;
