from plugins.base import BasePlugin

class NmapPlugin(BasePlugin):
    name = "nmap"
    async def execute(self, target: str, websocket=None) -> dict:
        return await self.run_command(["nmap", "-sV", target], websocket)