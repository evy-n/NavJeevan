from plugins.base import BasePlugin

class FfufPlugin(BasePlugin):
    name = "ffuf"
    async def execute(self, target: str, websocket=None) -> dict:
        # ffuf ko ek wordlist chahiye hoti hai. Hum default use kar rahe hain.
        return await self.run_command(["ffuf", "-u", f"{target}/FUZZ", "-w", "/usr/share/wordlists/dirb/common.txt", "-mc", "200,204,301,302", "-s"], websocket)