import subprocess
from pathlib import Path

def run(emfit_dir: Path):
    # Runs the bash preprocessing script.
    # Sets up directory structure, strips Emfit suffixes,
    # migrates files to data/raw/, and classifies files into subfolders.

    script_path = Path(__file__).parent.parent / "preprocessing_script.sh"

    if not script_path.exists():
        raise FileNotFoundError(f"Preprocessing script not found at: {script_path}")
    
    print(f"Running preprocessing script: {script_path}")

    result = subprocess.run(
        ["C:/Program Files/Git/bin/bash.exe", str(script_path)],
        capture_output=True,
        text=True,
        cwd=str(emfit_dir) # Run from the EMFIT directory.
    )

    if result.stdout:
        print(result.stdout)

    if result.returncode == 0:
        print("Preprocessing script completed successfully.")
    else:
        print("Preprocessing script failed:")
        print(result.stderr)
        print(result.stdout)
        raise RuntimeError("preprocessing_script.sh failed")

if __name__ == "__main__":
    emfit_dir = Path("C:/Users/ryadl/Desktop/EMFIT_local/Emfit_1")
    run(emfit_dir)