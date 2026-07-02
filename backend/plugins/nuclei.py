from plugins.base import BasePlugin

class NucleiPlugin(BasePlugin):
    name = "nuclei"
    async def execute(self, target: str) -> dict:
        return await self.run_command(["nuclei", "-u", target, "-silent"])