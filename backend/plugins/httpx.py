from plugins.base import BasePlugin

class HttpxPlugin(BasePlugin):
    name = "httpx"
    async def execute(self, target: str) -> dict:
        return await self.run_command(["httpx", "-u", target, "-status-code", "-title", "-silent"])