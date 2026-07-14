#!/usr/bin/env python3
"""
ClipCrafter - Cortador Inteligente de Clipes Virais
Corte os melhores momentos das suas lives com detecção automática de fatores virais.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import ClipCrafterApp

def main():
    app = ClipCrafterApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

if __name__ == "__main__":
    main()
