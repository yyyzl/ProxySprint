; 只安装本应用到当前用户目录；测速设置和报告位于独立的数据目录。
#ifndef AppVersion
  #error 必须通过 scripts/build_installer.py 指定版本和程序目录
#endif

[Setup]
AppId={{998697B5-563B-49EA-A210-C680D490DB28}
; 保留安装身份和默认目录，使 NodeScope 用户直接覆盖升级。
AppName=ProxySprint
AppVersion={#AppVersion}
AppVerName=ProxySprint {#AppVersion}
AppPublisher=yyyzl
AppPublisherURL=https://github.com/yyyzl/ProxySprint
AppSupportURL=https://github.com/yyyzl/ProxySprint/issues
AppUpdatesURL=https://github.com/yyyzl/ProxySprint/releases
VersionInfoVersion={#AppVersion}.{#AppBuild}
DefaultDirName={localappdata}\Programs\NodeScope
DefaultGroupName=ProxySprint
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=no
DisableWelcomePage=no
DisableProgramGroupPage=yes
WizardStyle=modern
SetupIconFile=..\..\desktop\windows\runner\resources\app_icon.ico
UninstallDisplayIcon={app}\ProxySprint.exe
OutputDir={#OutputDir}
OutputBaseFilename=ProxySprint-Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
chinesesimplified.DesktopShortcut=创建桌面快捷方式
chinesesimplified.LaunchProxySprint=启动 ProxySprint · 代理节点测速
chinesesimplified.UninstallProxySprint=卸载 ProxySprint
english.DesktopShortcut=Create a desktop shortcut
english.LaunchProxySprint=Launch ProxySprint
english.UninstallProxySprint=Uninstall ProxySprint

[Messages]
chinesesimplified.ConfirmUninstall=确定卸载 %1 吗？%n%n本机设置和测速报告会保留。
english.ConfirmUninstall=Uninstall %1?%n%nYour settings and test reports will be kept.

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\ProxySprint\ProxySprint"; Filename: "{app}\ProxySprint.exe"; WorkingDir: "{app}"
Name: "{userprograms}\ProxySprint\{cm:UninstallProxySprint}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\ProxySprint"; Filename: "{app}\ProxySprint.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[InstallDelete]
; 仅移除旧版本的程序入口，不触碰设置、报告或其他应用。
Type: files; Name: "{app}\NodeScope.exe"
Type: files; Name: "{userprograms}\NodeScope\NodeScope.lnk"
Type: files; Name: "{userprograms}\NodeScope\卸载 NodeScope.lnk"
Type: files; Name: "{userprograms}\NodeScope\Uninstall NodeScope.lnk"
Type: dirifempty; Name: "{userprograms}\NodeScope"
Type: files; Name: "{userdesktop}\NodeScope.lnk"

[Run]
Filename: "{app}\ProxySprint.exe"; Description: "{cm:LaunchProxySprint}"; Flags: nowait postinstall skipifsilent
