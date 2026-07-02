from plugins.base import BasePlugin

class GauPlugin(BasePlugin):
    name = "gau"
    async def execute(self, target: str) -> dict:
        return await self.run_command(["gau", target])