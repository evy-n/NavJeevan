import subprocess
import time

class ToolEngine:
    def run_command(self, command_list, retries=1):
        """Asli system command ko run karta hai with Retry Logic"""
        attempt = 0
        while attempt <= retries:
            try:
                result = subprocess.run(command_list, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    return {"status": "Completed", "output": result.stdout}
                else:
                    if attempt < retries:
                        time.sleep(2) # Wait before retry
                        attempt += 1
                        continue
                    return {"status": "Failed", "error": result.stderr}
            except subprocess.TimeoutExpired:
                if attempt < retries:
                    time.sleep(2)
                    attempt += 1
                    continue
                return {"status": "Failed", "error": "Command timed out (120s)"}
            except FileNotFoundError:
                return {"status": "Failed", "error": "Tool not installed."}
            except Exception as e:
                return {"status": "Failed", "error": str(e)}
        return {"status": "Failed", "error": "Max retries exceeded"}

    # Self-Recovery: Agar tool fail ho, toh alternative try karo
    def execute_with_fallback(self, tool_name, target):
        if tool_name == "nmap":
            res = self.run_command(["nmap", "-sV", target])
            if res["status"] == "Failed":
                res = self.run_command(["naabu", "-host", target, "-silent"]) # Fallback
            return res
            
        elif tool_name == "subfinder":
            res = self.run_command(["subfinder", "-d", target, "-silent"])
            if res["status"] == "Failed":
                res = self.run_command(["assetfinder", target]) # Fallback
            return res
            
        elif tool_name == "httpx":
            return self.run_command(["httpx", "-u", target, "-status-code", "-title", "-silent"])
        elif tool_name == "katana":
            return self.run_command(["katana", "-u", target, "-d", "2", "-silent"])
        elif tool_name == "gau":
            return self.run_command(["gau", target])
        elif tool_name == "naabu":
            return self.run_command(["naabu", "-host", target, "-silent"])
        elif tool_name == "nuclei":
            return self.run_command(["nuclei", "-u", target, "-silent"])
        else:
            return {"status": "Failed", "error": "Invalid tool"}

tool_engine = ToolEngine()