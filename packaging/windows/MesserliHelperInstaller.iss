#define MyDistDir AddBackslash(SourcePath) + "..\\..\\dist\\MesserliHelper"
#define MyOutputDir AddBackslash(SourcePath) + "..\\..\\dist\\installer"
#define MyIconFile AddBackslash(SourcePath) + "app.ico"

#include "installer_metadata.iss"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppInstallDirName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousLanguage=yes
UsePreviousTasks=yes
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#MyIconFile}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyAppSetupBaseName}-{#MyAppVersion}
ArchitecturesAllowed=x86compatible
ChangesAssociations=no
CloseApplications=force

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; AppUserModelID: "{#MyAppUserModelID}"; Check: not WizardNoIcons
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; Check: not WizardNoIcons
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "{#MyAppUserModelID}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent unchecked

[CustomMessages]
english.DeleteAppDataPrompt=Delete the local application data as well?%n%n%1%n%nThis removes saved days, templates, preferences and logs.
english.DeleteAppDataFailed=The local application data could not be deleted completely:%n%1
german.DeleteAppDataPrompt=Soll der lokale Datenordner ebenfalls gelöscht werden?%n%n%1%n%nDies entfernt gespeicherte Tage, Vorlagen, Einstellungen und Logs.
german.DeleteAppDataFailed=Der lokale Datenordner konnte nicht vollständig gelöscht werden:%n%1

[Code]
function GetAppDataDir: String;
begin
  Result := ExpandConstant('{localappdata}\{#MyAppDataDirName}');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  if UninstallSilent then
  begin
    Log('Silent uninstall detected; keeping user data.');
    Exit;
  end;

  AppDataDir := GetAppDataDir();
  if not DirExists(AppDataDir) then
    Exit;

  if MsgBox(
    FmtMessage(CustomMessage('DeleteAppDataPrompt'), [AppDataDir]),
    mbConfirmation,
    MB_YESNO or MB_DEFBUTTON2
  ) = IDYES then
  begin
    if DelTree(AppDataDir, True, True, True) then
      Log('Deleted user data directory: ' + AppDataDir)
    else
      MsgBox(
        FmtMessage(CustomMessage('DeleteAppDataFailed'), [AppDataDir]),
        mbInformation,
        MB_OK
      );
  end;
end;
