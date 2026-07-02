from plugins.base import BasePlugin
import asyncio

# Doc 36 & 96: Universal Tool Registry
# Format: "tool_name": ["command", "args", "with", "{target}"]
TOOL_CONFIGS = {
    # 1. Subdomain Discovery (8)
    "subfinder": ["subfinder", "-d", "{target}", "-silent"],
    "amass": ["amass", "enum", "-d", "{target}"],
    "assetfinder": ["assetfinder", "{target}"],
    "findomain": ["findomain", "-t", "{target}"],
    "chaos": ["chaos", "-d", "{target}", "-silent"],
    "ctfr": ["ctfr", "-d", "{target}"],
    "github-subdomains": ["github-subdomains", "-d", "{target}"],
    
    # 2. DNS Intelligence (7)
    "dnsx": ["dnsx", "-d", "{target}", "-silent"],
    "dig": ["dig", "{target}"],
    "nslookup": ["nslookup", "{target}"],
    "host": ["host", "{target}"],
    "massdns": ["massdns", "-r", "resolvers.txt", "-t", "A", "{target}"],
    "dnsgen": ["dnsgen", "{target}"],
    "shuffledns": ["shuffledns", "-d", "{target}"],
    
    # 3. Live Host Discovery (5)
    "httpx": ["httpx", "-u", "{target}", "-status-code", "-title", "-silent"],
    "httprobe": ["httprobe", "{target}"],
    "curl": ["curl", "-I", "{target}"],
    "wget": ["wget", "-qO-", "{target}"],
    "netcat": ["nc", "-vz", "{target}", "80"],
    
    # 4. Port Discovery (6)
    "naabu": ["naabu", "-host", "{target}", "-silent"],
    "nmap": ["nmap", "-sV", "{target}"],
    "rustscan": ["rustscan", "-a", "{target}"],
    "masscan": ["masscan", "{target}", "-p1-65535"],
    "unicornscan": ["unicornscan", "{target}"],
    
    # 5. Crawling (8)
    "katana": ["katana", "-u", "{target}", "-d", "2", "-silent"],
    "hakrawler": ["hakrawler", "-u", "{target}"],
    "gospider": ["gospider", "-s", "{target}"],
    "gau": ["gau", "{target}"],
    "waybackurls": ["waybackurls", "{target}"],
    
    # 6. Directory / Content Discovery (8)
    "ffuf": ["ffuf", "-u", "{target}/FUZZ", "-w", "wordlist.txt", "-s"],
    "feroxbuster": ["feroxbuster", "-u", "{target}"],
    "dirsearch": ["dirsearch", "-u", "{target}"],
    "gobuster": ["gobuster", "dir", "-u", "{target}", "-w", "wordlist.txt"],
    "wfuzz": ["wfuzz", "-w", "wordlist.txt", "{target}/FUZZ"],
    "dirb": ["dirb", "{target}"],
    
    # 7. Parameter Discovery (5)
    "arjun": ["arjun", "-u", "{target}"],
    "paramspider": ["paramspider", "-d", "{target}"],
    
    # 8. JavaScript Intelligence (8)
    "linkfinder": ["linkfinder", "-i", "{target}"],
    "secretfinder": ["secretfinder", "-i", "{target}"],
    "jsparser": ["jsparser", "-u", "{target}"],
    "jsluice": ["jsluice", "url", "{target}"],
    "xnlinkfinder": ["xnLinkFinder", "-i", "{target}"],
    
    # 9. Technology Fingerprinting (6)
    "wappalyzer": ["wappalyzer", "{target}"],
    "whatweb": ["whatweb", "{target}"],
    "builtwith": ["builtwith", "{target}"],
    "cmseek": ["cmseek", "-u", "{target}"],
    "wpscan": ["wpscan", "--url", "{target}"],
    
    # 10. API Discovery (7)
    "graphql-voyager": ["graphql-voyager", "-u", "{target}"],
    "swagger-parser": ["swagger-parser", "-u", "{target}"],
    
    # 11. Vulnerability Detection (8)
    "nuclei": ["nuclei", "-u", "{target}", "-silent"],
    "nikto": ["nikto", "-h", "{target}"],
    "nmap-nse": ["nmap", "-sC", "-sV", "{target}"],
    "sslyze": ["sslyze", "{target}"],
    "testssl": ["testssl.sh", "{target}"],
    
    # 12. Secrets Discovery (5)
    "trufflehog": ["trufflehog", "git", "remote", "{target}"],
    "gitleaks": ["gitleaks", "detect", "--source", "{target}"],
    "detect-secrets": ["detect-secrets", "scan", "{target}"],
    
    # 13. TLS / SSL Analysis (5)
    "openssl": ["openssl", "s_client", "-connect", "{target}:443"],
    
    # 14. Visual Recon (4)
    "eyewitness": ["eyewitness", "--web", "-f", "{target}"],
    "aquatone": ["aquatone", "-u", "{target}"],
}

# Map tools to categories for UI
TOOL_CATEGORIES = {
    "Subdomain Discovery": ["subfinder", "amass", "assetfinder", "findomain", "chaos", "ctfr", "github-subdomains"],
    "DNS Intelligence": ["dnsx", "dig", "nslookup", "host", "massdns", "dnsgen", "shuffledns"],
    "Live Host Discovery": ["httpx", "httprobe", "curl", "wget", "netcat"],
    "Port Discovery": ["naabu", "nmap", "rustscan", "masscan", "unicornscan"],
    "Crawling": ["katana", "hakrawler", "gospider", "gau", "waybackurls"],
    "Content Discovery": ["ffuf", "feroxbuster", "dirsearch", "gobuster", "wfuzz", "dirb"],
    "Parameter Discovery": ["arjun", "paramspider"],
    "JavaScript Intelligence": ["linkfinder", "secretfinder", "jsparser", "jsluice", "xnlinkfinder"],
    "Technology Fingerprinting": ["wappalyzer", "whatweb", "builtwith", "cmseek", "wpscan"],
    "API Discovery": ["graphql-voyager", "swagger-parser"],
    "Vulnerability Detection": ["nuclei", "nikto", "nmap-nse", "sslyze", "testssl"],
    "Secrets Discovery": ["trufflehog", "gitleaks", "detect-secrets"],
    "TLS/SSL Analysis": ["openssl"],
    "Visual Recon": ["eyewitness", "aquatone"]
}

class GenericPlugin(BasePlugin):
    def __init__(self, name, cmd_args):
        self.name = name
        self.cmd_args = cmd_args
        
    async def execute(self, target: str, websocket=None) -> dict:
        # Replace {target} with actual target
        command = [arg.replace("{target}", target) for arg in self.cmd_args]
        return await self.run_command(command, websocket)

class PluginManager:
    def __init__(self):
        self.registry = {}
        # Dynamically register all tools
        for name, cmd_args in TOOL_CONFIGS.items():
            self.registry[name] = GenericPlugin(name, cmd_args)
    
    def get_plugin(self, tool_name: str):
        return self.registry.get(tool_name)

plugin_manager = PluginManager()