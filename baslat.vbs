Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\Administrator\.gemini\antigravity\scratch\uyap_tahliye_kontrol"
WshShell.Run "python gui.py", 0, False

