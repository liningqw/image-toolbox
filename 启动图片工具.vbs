Option Explicit
Dim fso, shell, base
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(base & "\.venv\Scripts\pythonw.exe") Then
    MsgBox "Python virtual environment not found. Please follow README.md to install dependencies.", 48, "Image Tool"
    WScript.Quit 1
End If
shell.CurrentDirectory = base
shell.Run """" & base & "\.venv\Scripts\pythonw.exe"" -m imgtool.gui", 0, False
