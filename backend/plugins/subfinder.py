from plugins.base import BasePlugin

class SubfinderPlugin(BasePlugin):
    name = "subfinder"
    async def execute(self, target: str, websocket=None) -> dict:
        return await self.run_command(["subfinder", "-d", target, "-silent"], websocket)