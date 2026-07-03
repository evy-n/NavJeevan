from plugins.base import BasePlugin
import asyncio

TOOL_CONFIGS = {
    "subfinder": ["subfinder", "-d", "{target}", "-silent"],
    "httpx": ["httpx", "-u", "{target}", "-status-code", "-title", "-silent"],
    "nuclei": ["nuclei", "-u", "{target}", "-silent"],
    "nmap": ["nmap", "-sV", "{target}"],
    "katana": ["katana", "-u", "{target}", "-d", "2", "-silent"],
    "gau": ["gau", "{target}"],
    "naabu": ["naabu", "-host", "{target}", "-silent"],
    "ffuf": ["ffuf", "-u", "{target}/FUZZ", "-w", "wordlist.txt", "-s"],
}

# P3.11: Fallback logic migrated from tool_engine.py
FALLBACK_CONFIGS = {
    "nmap": ["naabu", "-host", "{target}", "-silent"],
    "subfinder": ["assetfinder", "{target}"]
}

TOOL_CATEGORIES = {
    "Recon": ["subfinder", "httpx", "gau", "katana", "nmap", "naabu", "ffuf"]
}

class GenericPlugin(BasePlugin):
    def __init__(self, name, cmd_args):
        self.name = name
        self.cmd_args = cmd_args
        
    async def execute(self, target: str, websocket=None) -> dict:
        # Replace target placeholder
        command = [arg.replace("{target}", target) for arg in self.cmd_args]
        result = await self.run_command(command, websocket)
        
        # If failed and fallback exists
        if result["status"] != "Completed" and self.name in FALLBACK_CONFIGS:
            if websocket:
                await websocket.send_text(f"[!] Fallback: Trying alternative command for {self.name}...")
            fallback_cmd = [arg.replace("{target}", target) for arg in FALLBACK_CONFIGS[self.name]]
            result = await self.run_command(fallback_cmd, websocket)
            
        return result

class PluginManager:
    def __init__(self):
        self.registry = {}
        for name, cmd_args in TOOL_CONFIGS.items():
            self.registry[name] = GenericPlugin(name, cmd_args)
    
    def get_plugin(self, tool_name: str):
        return self.registry.get(tool_name)

plugin_manager = PluginManager()