"""Verify the run entry refuses an open GUI. Never permit a device connection in this check."""
import subprocess
import sys
from pathlib import Path

import runner


def main():
    if not runner.maa_gui_running():
        raise RuntimeError("The GUI guard cannot be verified because MAA.exe is not running")
    # Force the GUI guard in the child too; a GUI closing during this test must
    # never turn this read-only verification into a live run.
    code = "import runner;runner.maa_gui_running=lambda:True;runner.sys.argv=['runner.py','--run'];runner.main()"
    result = subprocess.run([sys.executable,"-B","-c",code],cwd=Path(__file__).resolve().parent,
                            capture_output=True,text=True,encoding="utf-8",timeout=20)
    if result.returncode == 0 or "MAA.exe is open" not in result.stderr:
        raise RuntimeError("Run entry guard did not fail as expected: " + result.stdout + result.stderr)
    print("PASS: live entry rejected the open MAA GUI before loading core or connecting the device.")


if __name__ == "__main__":
    main()
