import sys
import os

possible_paths = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".agents", "skills", "adaptive-ontological-search", "scripts")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "scripts")),
]
for p in possible_paths:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
