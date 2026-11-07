from pathlib import Path
import os
import sys
import PySide6

qt_directory = Path(PySide6.__file__).parent
runtime_names = ("vcruntime140.dll", "vcruntime140_1.dll")

# Keep unrelated programs' DLLs out of dependency discovery.
os.environ["PATH"] = os.pathsep.join([
    str(Path(sys.executable).parent),
    sys.base_prefix,
    str(Path(sys.base_prefix) / "DLLs"),
    str(qt_directory),
    str(Path(os.environ["SystemRoot"]) / "System32"),
    os.environ["SystemRoot"],
])

a = Analysis(
    ["app/main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=[("assets/mark.svg", "assets"), ("assets/desk.svg", "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)

# Python 3.12 can ship an older C++ runtime than Qt needs. Load the runtime
# supplied with our pinned Qt wheel before Python or Qt imports its DLLs.
for name in runtime_names:
    runtime = qt_directory / name
    if not runtime.is_file():
        raise RuntimeError(f"Required Qt runtime is missing: {runtime}")
    a.binaries = [
        entry for entry in a.binaries
        if Path(entry[0]).name.lower() != name
    ]
    a.binaries.append((name, str(runtime), "BINARY"))

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="TidyDesk", console=False, debug=False, strip=False, upx=False,
    icon="assets/TidyDesk.ico",
)
