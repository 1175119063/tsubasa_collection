#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif
#ifndef MySourceDir
  #define MySourceDir "release\翼·时光记-Windows-v0.2.0-空白版"
#endif

[Setup]
AppId={{3E3440B8-24C9-47C0-98EE-51D2661D2B89}
AppName=翼·时光记
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Tsubasa
DefaultGroupName=翼·时光记
OutputBaseFilename=翼·时光记-Windows-v{#MyAppVersion}-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayIcon={app}\翼·时光记.exe
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Excludes: "data\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MySourceDir}\data\*"; DestDir: "{app}\data"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs uninsneveruninstall

[Dirs]
Name: "{app}\data"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{app}\backups"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "{app}\updates"; Permissions: users-modify; Flags: uninsneveruninstall

[Icons]
Name: "{group}\翼·时光记"; Filename: "{app}\翼·时光记.exe"
Name: "{autodesktop}\翼·时光记"; Filename: "{app}\翼·时光记.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Run]
Filename: "{app}\翼·时光记.exe"; Description: "启动翼·时光记"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 用户资料、备份与已下载更新不会在卸载时删除。
Type: filesandordirs; Name: "{app}\_internal"
