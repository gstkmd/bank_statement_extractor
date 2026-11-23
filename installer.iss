[Setup]
AppName=ShieldDocs
AppVersion=v1.1.41
DefaultDirName={autopf}\ShieldDocs
DefaultGroupName=ShieldDocs
OutputDir=obfuscated_src\dist
OutputBaseFilename=ShieldDocs_Setup_v1.1.41
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin

[Files]
Source: "obfuscated_src\dist\ShieldDocs\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ShieldDocs"; Filename: "{app}\ShieldDocs.exe"
Name: "{autodesktop}\ShieldDocs"; Filename: "{app}\ShieldDocs.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\ShieldDocs.exe"; Description: "Launch ShieldDocs"; Flags: nowait postinstall
