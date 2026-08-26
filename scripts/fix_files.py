import json, pathlib

data = pathlib.Path(r"C:\Trading\Alpha\data\live")

# 1. Clear errors.json
(data / "errors.json").write_text(json.dumps([]), encoding="utf-8")
print("errors.json cleared")

# 2. Write error_response.json
(data / "error_response.json").write_text(json.dumps({
    "diagnosis": "action.json contained UTF-16 LE BOM (0xFF byte at position 0) from PowerShell echo redirect. daemon.py _process_actions() opened with encoding=utf-8 which cannot decode BOM bytes. Exception handler caught only JSONDecodeError and OSError, not UnicodeDecodeError, so the uncaught exception crashed the daemon.",
    "action_taken": "Fixed daemon.py line 585: encoding=utf-8 to utf-8-sig (auto-strips UTF-8 BOM). Fixed line 587: added UnicodeDecodeError to except clause as safety net for any other encoding issue. Wrote clean action.json via Python. Cleared errors.json.",
    "pause_trading": False,
    "needs_human": False
}, indent=2), encoding="utf-8")
print("error_response.json written")

# 3. Verify action.json is clean
aj = json.loads((data / "action.json").read_text(encoding="utf-8"))
print(f"action.json OK: decision={aj.get('decision')} symbol={aj.get('symbol')}")

# 4. Verify all files are BOM-free
for fname in ["action.json", "errors.json", "error_response.json"]:
    raw = (data / fname).read_bytes()
    if raw[:3] == b'\xef\xbb\xbf':
        print(f"WARNING: {fname} has UTF-8 BOM!")
    elif raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        print(f"WARNING: {fname} has UTF-16 BOM!")
    else:
        print(f"{fname}: clean UTF-8, no BOM")
