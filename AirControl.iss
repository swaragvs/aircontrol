#define MyAppName "AirControl"
#define MyAppVersion "1.0.0"

[Setup]
AppId={{8A6A62F4-9F89-46A6-92E4-1B67D00F5401}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppMutex=AirControlTray
DefaultDirName={autopf}\AirControl
DefaultGroupName=AirControl
OutputDir=dist
OutputBaseFilename=AirControl-Setup
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\AirControl.exe
CloseApplications=yes
CloseApplicationsFilter=AirControl.exe

[Files]
Source: "dist\AirControl\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\AirControl"; Filename: "{app}\AirControl.exe"

[Tasks]
Name: "autostart"; Description: "Start AirControl with Windows"; Flags: checkedonce

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AirControl"; ValueData: """{app}\AirControl.exe"" --background"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""AirControl"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""AirControl"" dir=in action=allow program=""{app}\AirControl.exe"" enable=yes profile=private"; Flags: runhidden
Filename: "{app}\AirControl.exe"; Description: "Start AirControl now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM AirControl.exe"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""AirControl"""; Flags: runhidden

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  MarkerPath: string;
begin
  if (CurStep = ssPostInstall) and not WizardIsTaskSelected('autostart') then
  begin
    MarkerPath := ExpandConstant('{userappdata}\AirControl\.autostart_set');
    ForceDirectories(ExtractFileDir(MarkerPath));
    SaveStringToFile(MarkerPath, '', False);
  end;
end;
