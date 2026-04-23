; FPX Timetracker – Inno Setup Installer
; Build:  ISCC.exe /DAppVersion=0.1.0 build\installer.iss

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName      "FPX Timetracker"
#define AppPublisher "Fourplex"
#define AppExeName   "FPXTimetracker.exe"

[Setup]
AppId={{E1F05DAE-2B4A-4DE0-9C2C-FPXWIN000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\FPXTimetracker
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=FPXTimetracker-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Verknüpfungen:"; Flags: checkedonce
Name: "autostart";  Description: "Automatisch mit Windows starten";  GroupDescription: "Start:"; Flags: unchecked

[Files]
Source: "..\dist\FPXTimetracker.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LIES MICH.txt";           DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\assets\app.ico";          DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FPXTimetracker"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{#AppName} jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Laufende Instanz vor Deinstallation beenden
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#AppExeName} /T"; Flags: runhidden

[Code]
var
  DeleteDataPage: TInputOptionWizardPage;

procedure InitializeUninstallProgressForm();
begin
  // Nichts weiter – Uninstall läuft normal.
end;

function InitializeUninstall(): Boolean;
var
  MsgResult: Integer;
begin
  MsgResult := MsgBox(
    'Möchtest du zusätzlich alle Benutzerdaten' + #13#10 +
    '(API-Key, Sessions, Einstellungen) löschen?' + #13#10 + #13#10 +
    'Speicherort: %APPDATA%\FPXTimetracker',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
  if MsgResult = IDYES then begin
    DelTree(ExpandConstant('{userappdata}\FPXTimetracker'), True, True, True);
  end;
  Result := True;
end;
