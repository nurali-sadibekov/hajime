; Inno Setup script. Built by build.bat:  iscc /DAppVersion=1.2.0 installer\hajime.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1B7E52-2B0C-4C3E-9F58-3D9A4E1A7C21}
AppName=Hajime
AppVersion={#AppVersion}
AppVerName=Hajime {#AppVersion}
AppPublisher=Hajime
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Hajime
DefaultGroupName=Hajime
DisableProgramGroupPage=yes
; Installs for the current user by default (no administrator rights needed); the wizard
; offers an all-users install when run as administrator.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=Hajime-Setup
SetupIconFile=..\packaging\hajime.ico
UninstallDisplayIcon={app}\Hajime.exe
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Hajime\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Hajime"; Filename: "{app}\Hajime.exe"
Name: "{autodesktop}\Hajime"; Filename: "{app}\Hajime.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Hajime.exe"; Description: "Launch Hajime"; Flags: nowait postinstall skipifsilent

; Uninstalling removes the program only. Tasks and the signed-in session live in
; %APPDATA%\Hajime and are deliberately kept.
