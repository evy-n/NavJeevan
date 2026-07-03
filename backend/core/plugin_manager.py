from plugins.base import BasePlugin
import asyncio

# Full 90+ Tool Registry
TOOL_CONFIGS = {
    # 1. Subdomain Discovery (7)
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
    
    # 4. Port Discovery (5)
    "naabu": ["naabu", "-host", "{target}", "-silent"],
    "nmap": ["nmap", "-sV", "{target}"],
    "rustscan": ["rustscan", "-a", "{target}"],
    "masscan": ["masscan", "{target}", "-p1-65535"],
    "unicornscan": ["unicornscan", "{target}"],
    
    # 5. Crawling (5)
    "katana": ["katana", "-u", "{target}", "-d", "2", "-silent"],
    "hakrawler": ["hakrawler", "-u", "{target}"],
    "gospider": ["gospider", "-s", "{target}"],
    "gau": ["gau", "{target}"],
    "waybackurls": ["waybackurls", "{target}"],
    
    # 6. Directory / Content Discovery (6)
    "ffuf": ["ffuf", "-u", "{target}/FUZZ", "-w", "wordlist.txt", "-s"],
    "feroxbuster": ["feroxbuster", "-u", "{target}"],
    "dirsearch": ["dirsearch", "-u", "{target}"],
    "gobuster": ["gobuster", "dir", "-u", "{target}", "-w", "wordlist.txt"],
    "wfuzz": ["wfuzz", "-w", "wordlist.txt", "{target}/FUZZ"],
    "dirb": ["dirb", "{target}"],
    
    # 7. Parameter Discovery (2)
    "arjun": ["arjun", "-u", "{target}"],
    "paramspider": ["paramspider", "-d", "{target}"],
    
    # 8. JavaScript Intelligence (5)
    "linkfinder": ["linkfinder", "-i", "{target}"],
    "secretfinder": ["secretfinder", "-i", "{target}"],
    "jsparser": ["jsparser", "-u", "{target}"],
    "jsluice": ["jsluice", "url", "{target}"],
    "xnlinkfinder": ["xnLinkFinder", "-i", "{target}"],
    
    # 9. Technology Fingerprinting (5)
    "wappalyzer": ["wappalyzer", "{target}"],
    "whatweb": ["whatweb", "{target}"],
    "builtwith": ["builtwith", "{target}"],
    "cmseek": ["cmseek", "-u", "{target}"],
    "wpscan": ["wpscan", "--url", "{target}"],
    
    # 10. API Discovery (2)
    "graphql-voyager": ["graphql-voyager", "-u", "{target}"],
    "swagger-parser": ["swagger-parser", "-u", "{target}"],
    
    # 11. Vulnerability Detection (6)
    "nuclei": ["nuclei", "-u", "{target}", "-silent"],
    "nikto": ["nikto", "-h", "{target}"],
    "nmap-nse": ["nmap", "-sC", "-sV", "{target}"],
    "sslyze": ["sslyze", "{target}"],
    "testssl": ["testssl.sh", "{target}"],
    # FIX 1: dalfox added here
    "dalfox": ["dalfox", "url", "{target}", "--silence"],
    
    # 12. Secrets Discovery (3)
    "trufflehog": ["trufflehog", "git", "remote", "{target}"],
    "gitleaks": ["gitleaks", "detect", "--source", "{target}"],
    "detect-secrets": ["detect-secrets", "scan", "{target}"],
    
    # 13. TLS / SSL Analysis (1)
    "openssl": ["openssl", "s_client", "-connect", "{target}:443"],
    
    # 14. Visual Recon (2)
    "eyewitness": ["eyewitness", "--web", "-f", "{target}"],
    "aquatone": ["aquatone", "-u", "{target}"]
}

# Full Category Mapping
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
    # FIX 1: dalfox added to category list
    "Vulnerability Detection": ["nuclei", "nikto", "nmap-nse", "sslyze", "testssl", "dalfox"],
    "Secrets Discovery": ["trufflehog", "gitleaks", "detect-secrets"],
    "TLS/SSL Analysis": ["openssl"],
    "Visual Recon": ["eyewitness", "aquatone"]
}

# Fallback logic kept intact
FALLBACK_CONFIGS = {
    "nmap": ["naabu", "-host", "{target}", "-silent"],
    "subfinder": ["assetfinder", "{target}"]
}

class GenericPlugin(BasePlugin):
    def __init__(self, name, cmd_args):
        self.name = name
        self.cmd_args = cmd_args
        
    async def execute(self, target: str, websocket=None) -> dict:
        command = [arg.replace("{target}", target) for arg in self.cmd_args]
        result = await self.run_command(command, websocket)
        
        if result["status"] != "Completed" and self.name in FALLBACK_CONFIGS:
            if websocket:
                await websocket.send_text(f"[!] Fallback: Trying alternative command for {self.name}...")
            fallback_cmd = [arg.replace("{target}", target) for arg in FALLBACK_CONFIGS[self.name]]
            result = await self.run_command(fallback_cmd, websocket)
            
        return result

class PluginManager:
    def __init__(self):
        self.registry = {}
        for name, cmd_args in TOOL_CONFIGS.items():
            self.registry[name] = GenericPlugin(name, cmd_args)
    
    def get_plugin(self, tool_name: str):
        return self.registry.get(tool_name)

plugin_manager = PluginManager()