from plugins.base import BasePlugin

class DalfoxPlugin(BasePlugin):
    name = "dalfox"
    async def execute(self, target: str, websocket=None) -> dict:
        return await self.run_command(["dalfox", "url", target, "--silence"], websocket)