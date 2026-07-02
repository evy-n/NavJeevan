from plugins.base import BasePlugin

class KatanaPlugin(BasePlugin):
    name = "katana"
    async def execute(self, target: str) -> dict:
        return await self.run_command(["katana", "-u", target, "-d", "2", "-silent"])