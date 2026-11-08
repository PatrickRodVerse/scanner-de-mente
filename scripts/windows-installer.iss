#ifndef AppSource
  #error AppSource must point to the staged application directory.
#endif
#ifndef RedistPath
  #error RedistPath must point to the verified Microsoft VC++ redistributable.
#endif
#ifndef OutputDir
  #error OutputDir must point to the installer output directory.
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId=ScannerDeMente
AppName=Scanner de Mente
AppVersion={#AppVersion}
AppPublisher=PatrickRodVerse
DefaultDirName={localappdata}\Programs\Scanner de Mente
DefaultGroupName=Scanner de Mente
UsePreviousAppDir=no
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile={#AppSource}\LICENSE
InfoAfterFile={#AppSource}\INSTALL.md
OutputDir={#OutputDir}
OutputBaseFilename=Scanner-de-Mente-Setup-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\runtime\python.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#RedistPath}"; DestName: "vc_redist.x64.exe"; Flags: dontcopy
Source: "{#AppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Scanner de Mente"; Filename: "{app}\runtime\python.exe"; Parameters: "-B -X utf8 -m lab.ui --open"; WorkingDir: "{app}"
Name: "{group}\Uninstall Scanner de Mente"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Scanner de Mente"; Filename: "{app}\runtime\python.exe"; Parameters: "-B -X utf8 -m lab.ui --open"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\python.exe"; Parameters: "-B -X utf8 -m lab.ui --open"; WorkingDir: "{app}"; Description: "Open Scanner de Mente"; Flags: postinstall nowait skipifsilent

[Code]
function RuntimeInstalled: Boolean;
var
  Installed, Major, Minor: Cardinal;
begin
  Result := False;
  if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) and
     RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Major', Major) and
     RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Minor', Minor) then
    Result := (Installed = 1) and (Major = 14) and (Minor >= 50);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if RuntimeInstalled then
    Exit;
  ExtractTemporaryFile('vc_redist.x64.exe');
  if not ShellExec('runas', ExpandConstant('{tmp}\vc_redist.x64.exe'),
     '/install /quiet /norestart', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
    Result := 'Microsoft Visual C++ Runtime setup could not start: ' + SysErrorMessage(ResultCode)
  else if ResultCode = 3010 then begin
    NeedsRestart := True;
    Result := 'Microsoft Visual C++ Runtime requires a restart. Restart Windows, then run this installer again.';
  end
  else if ResultCode <> 0 then
    Result := 'Microsoft Visual C++ Runtime setup failed (code ' + IntToStr(ResultCode) + ').'
  else if not RuntimeInstalled then
    Result := 'Microsoft Visual C++ Runtime could not be verified. Repair the runtime, then run this installer again.';
end;
