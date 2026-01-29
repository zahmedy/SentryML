import os
import sys


ROOT = os.path.dirname(__file__)
os.environ.setdefault("DATABASE_URL", "sqlite://")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
