from plugins.base import BasePlugin

class NaabuPlugin(BasePlugin):
    name = "naabu"
    async def execute(self, target: str) -> dict:
        return await self.run_command(["naabu", "-host", target, "-silent"])