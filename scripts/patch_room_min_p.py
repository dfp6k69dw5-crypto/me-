from pathlib import Path

path = Path("scripts/room_private_model.py")
text = path.read_text()
old = '            "min_p": 0.02,\n'
new = '            "min_p": 0.005,\n'
if old not in text:
    raise SystemExit("guarded min_p target not found")
if new in text:
    raise SystemExit("min_p diversity patch already present")
path.write_text(text.replace(old, new, 1))
print("ROOM MIN_P DIVERSITY PATCH: READY")
