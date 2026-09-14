"""
Pytest-Konfiguration: Projekt-Root zum sys.path hinzufügen,
damit 'from src...' Imports in allen Tests funktionieren.
"""
import os
import sys

# Projekt-Root (Parent von tests/) zum Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
