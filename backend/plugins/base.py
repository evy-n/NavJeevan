import asyncio
import subprocess
import sys
import threading
from abc import ABC, abstractmethod

ACTIVE_PROCESSES = {}

class BasePlugin(ABC):
    name: str = "unknown"
    cmd_args: list = []
    
    @abstractmethod
    async def execute(self, target: str, websocket=None, auth: dict = None) -> dict:
        pass

    async def run_command(self, command_list, websocket=None):
        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
                
            process = subprocess.Popen(
                command_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
                creationflags=creation_flags
            )
            
            if websocket:
                ACTIVE_PROCESSES[id(websocket)] = process
                
            output_lines = []
            loop = asyncio.get_event_loop()
            
            def kill_proc(p):
                if p.poll() is None:
                    p.kill()
            timer = threading.Timer(300, kill_proc, args=[process])
            timer.start()
            
            def sync_read_and_stream():
                while True:
                    line = process.stdout.readline()
                    if not line:
                        if process.poll() is not None:
                            break
                        continue
                    stripped = line.strip()
                    if stripped:
                        output_lines.append(stripped)
                        if websocket:
                            try:
                                future = asyncio.run_coroutine_threadsafe(websocket.send_text(stripped), loop)
                                future.result(timeout=5)
                            except Exception:
                                pass
                process.wait()
                return process.returncode
            
            returncode = await loop.run_in_executor(None, sync_read_and_stream)
            timer.cancel()
            
            if websocket and id(websocket) in ACTIVE_PROCESSES:
                del ACTIVE_PROCESSES[id(websocket)]
                
            if returncode == 0:
                return {"status": "Completed", "output": "\n".join(output_lines)}
            elif returncode == -9:
                return {"status": "TimedOut", "error": "Scan exceeded 5 min limit"}
            else:
                err = process.stderr.read()
                if websocket and err: 
                    try:
                        future = asyncio.run_coroutine_threadsafe(websocket.send_text(f"[Error] {err.strip()}"), loop)
                        future.result(timeout=5)
                    except: pass
                return {"status": "Failed", "error": err}
                
        except Exception as e:
            err_msg = f"Execution Error: {type(e).__name__} - {str(e)}"
            if websocket: await websocket.send_text(err_msg)
            return {"status": "Failed", "error": err_msg}

class GenericPlugin(BasePlugin):
    def __init__(self, name, cmd_args):
        self.name = name
        self.cmd_args = cmd_args
        
    async def execute(self, target: str, websocket=None, auth: dict = None) -> dict:
        command = [arg.replace("{target}", target) for arg in self.cmd_args]
        
        # AUTH HEADERS INJECTION
        if auth and auth.get("type") in ["cookie", "bearer"] and auth.get("value"):
            header_val = ""
            if auth["type"] == "cookie":
                header_val = f"Cookie: {auth['value']}"
            elif auth["type"] == "bearer":
                header_val = f"Authorization: Bearer {auth['value']}"
            
            # Only add headers to HTTP-based tools that support -H flag
            if self.name in ["httpx", "nuclei", "dalfox", "ffuf"]:
                command.extend(["-H", header_val])
        
        result = await self.run_command(command, websocket)
        
        # Fallback logic
        if result["status"] != "Completed" and self.name in FALLBACK_CONFIGS:
            if websocket:
                await websocket.send_text(f"[!] Fallback: Trying alternative command for {self.name}...")
            fallback_cmd = [arg.replace("{target}", target) for arg in FALLBACK_CONFIGS[self.name]]
            result = await self.run_command(fallback_cmd, websocket)
            
        return result

FALLBACK_CONFIGS = {
    "nmap": ["naabu", "-host", "{target}", "-silent"],
    "subfinder": ["assetfinder", "{target}"]
}