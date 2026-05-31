import sys
from pathlib import Path

# Put the tools/ dir on sys.path so ``import staghunt_tools`` resolves when
# pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
