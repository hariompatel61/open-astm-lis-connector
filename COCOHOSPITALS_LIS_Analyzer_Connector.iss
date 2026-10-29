; ============================================================
; COCOHOSPITALS LIS Analyzer Connector
; Production Installer v1.0.1
; ============================================================

#define MyAppName "COCOHOSPITALS LIS"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "COCOHOSPITALS"
#define MyAppExeName "COCOHOSPITALS-LIS-Analyzer-Connector.exe"
#define MyAppTaskName "COCOHOSPITALS LIS Analyzer Connector"

[Setup]
AppId={{7D7F7F0B-5B8B-4A5D-9E9B-7A1F4C230001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\COCOHOSPITALS\LIS Analyzer Connector
DefaultGroupName={#MyAppName}
OutputDir=installer-output
OutputBaseFilename=COCOHOSPITALS-LIS
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; ArchitecturesInstallIn64BitMode removed for universal 32-bit and 64-bit Windows compatibility
UninstallDisplayName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=COCOHOSPITALS LIS
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoVersion=1.0.1.0
ChangesAssociations=no

SetupIconFile=logo.ico

[Files]
; Package only static application files.
; Runtime logs/temp/cache are deliberately excluded because they can be
; locked by the running connector and must not be shipped.
Source: "desktop-app\dist\COCOHOSPITALS-LIS-Analyzer-Connector\*"; \
    DestDir: "{app}"; \
    Excludes: "logs\*;_listener_temp\*;_local_app_data\*"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\logs"
Name: "{app}\_listener_temp"
Name: "{app}\_local_app_data"

[Icons]
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\logo.ico"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\logo.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
; Standard per-machine startup entry ensuring automatic launch when Windows boots and user logs on
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue

[Run]
; Proactively remove any legacy scheduled task to prevent duplicate launches on boot
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""{#MyAppTaskName}"" /F"; Flags: runhidden waituntilterminated

; Launch the connector immediately after installation.
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Remove any legacy scheduled task during uninstall
Filename: "schtasks.exe"; Parameters: "/Delete /TN ""{#MyAppTaskName}"" /F"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveScheduledTask"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\_listener_temp"
Type: filesandordirs; Name: "{app}\_local_app_data"
