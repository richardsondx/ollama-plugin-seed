"""Run the Ollama plugin seed server. Usage: python3 scripts/run_server.py

Default port 11435, set OLLAMA_PLUGIN_PORT to change it.
State file defaults to data/state.json, set OLLAMA_PLUGIN_STATE
to change it. No Ollama server is required to run the admin UI
and the plugin loader, but chat tool use needs Ollama on 11434.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server.plugin_server import main  # noqa: E402

if __name__ == "__main__":
    main()
