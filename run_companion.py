#!/usr/bin/env python3
"""OmniCompanion — Run Script

Start the voice-first multimodal companion.
Launch this, then open http://localhost:5173 in Chrome.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.orchestrator.companion_v2 import main

if __name__ == "__main__":
    main()
