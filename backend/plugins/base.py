import asyncio
import subprocess
import sys
import threading
from abc import ABC, abstractmethod

ACTIVE_PROCESSES = {}

class BasePlugin(ABC):
    name: str = "unknown"
    
    @abstractmethod
    async def execute(self, target: str, websocket=None) -> dict:
        pass

    async def run_command(self, command_list, websocket=None):
        try:
            creation_flags = 0
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NO_WINDOW
                
            # BUG 2 FIX: shell=False to prevent Command Injection. Pass list directly.
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
            elif returncode == -9: # Killed by timer
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