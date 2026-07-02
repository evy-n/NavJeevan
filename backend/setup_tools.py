import shutil
import subprocess
import os
import sys

def check_and_install():
    print("--- NAVJEEVAN HYPER-AUTOMATED TOOL SETUP ---")
    
    # 0. Ensure Go Bin path is in PATH (Windows issue fix)
    go_bin_path = os.path.join(os.path.expanduser("~"), "go", "bin")
    if go_bin_path not in os.environ["PATH"]:
        os.environ["PATH"] += os.pathsep + go_bin_path
        
    # 1. Python Tools
    print("\n[1/4] Checking Python-based Tools...")
    py_tools = ["sqlmap", "dirsearch"]
    for tool in py_tools:
        if shutil.which(tool):
            print(f"[✅] {tool} is already installed.")
        else:
            print(f"[⏳] Installing {tool} via pip...")
            subprocess.run([sys.executable, "-m", "pip", "install", tool])

    # 2. Git-Based Tools (Nikto etc.)
    print("\n[2/4] Checking Git/Perl-based Tools...")
    if not os.path.exists("tools/nikto"):
        if shutil.which("git"):
            print("[⏳] Cloning Nikto repository...")
            os.makedirs("tools", exist_ok=True)
            subprocess.run(["git", "clone", "https://github.com/sullo/nikto.git", "tools/nikto"])
            print("[✅] Nikto cloned successfully! (Use 'perl tools/nikto/program/nikto.pl' to run)")
        else:
            print("[❌] Git not installed. Cannot clone Nikto.")
    else:
        print("[✅] Nikto is already cloned.")

    # 3. Go Tools (Fixed Paths & More Tools)
    print("\n[3/4] Checking Go-based Tools (ProjectDiscovery, FFUF, etc.)...")
    if not shutil.which("go"):
        print("[❌] Go (Golang) is NOT installed. Please download from https://go.dev/dl/")
    else:
        go_tools = {
            "subfinder": "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
            "httpx": "github.com/projectdiscovery/httpx/cmd/httpx@latest",
            "nuclei": "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
            "katana": "github.com/projectdiscovery/katana/cmd/katana@latest",
            "naabu": "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest",
            "gau": "github.com/lc/gau/v2/cmd/gau@latest",
            "ffuf": "github.com/ffuf/ffuf/v2@latest",
            "assetfinder": "github.com/tomnomnom/assetfinder@latest",
            "hakrawler": "github.com/hakluke/hakrawler@latest",
            "gobuster": "github.com/OJ/gobuster/v3@latest",
            "dalfox": "github.com/hahwul/dalfox/v2@latest",
            "waybackurls": "github.com/tomnomnom/waybackurls@latest",
            "gospider": "github.com/jaeles-project/gospider@latest",
            "dnsx": "github.com/projectdiscovery/dnsx/cmd/dnsx@latest",
            "tlsx": "github.com/projectdiscovery/tlsx/cmd/tlsx@latest",
            "anew": "github.com/tomnomnom/anew@latest",
            "qsreplace": "github.com/tomnomnom/qsreplace@latest"
        }
        for tool_name, go_path_url in go_tools.items():
            if shutil.which(tool_name):
                print(f"[✅] {tool_name} is already installed.")
            else:
                print(f"[⏳] {tool_name} is missing. Installing automatically...")
                try:
                    subprocess.run(["go", "install", go_path_url], check=True)
                    print(f"[✅] {tool_name} installed successfully!")
                except Exception as e:
                    print(f"[❌] Failed to install {tool_name}: {e}")

    # 4. System Tools
    print("\n[4/4] Checking System Tools...")
    sys_tools = ["nmap", "masscan", "ruby", "git"]
    for tool in sys_tools:
        if shutil.which(tool):
            print(f"[✅] {tool} is installed.")
        else:
            if tool == "nmap": print(f"[❌] {tool} missing. Download from nmap.org")
            elif tool == "masscan": print(f"[❌] {tool} missing. Download from github.com/robertdavidgraham/masscan")
            elif tool == "ruby": print(f"[❌] {tool} missing. Required for real WPScan.")
            else: print(f"[❌] {tool} missing.")

    # Nuclei templates update
    if shutil.which("nuclei"):
        print("\n[⏳] Updating Nuclei templates...")
        subprocess.run(["nuclei", "-update-templates"])
        print("[✅] Nuclei templates updated.")

    print("\n--- SETUP COMPLETE! ---")
    print("WARNING: Close and reopen your terminal/server so PATH updates take effect.")

if __name__ == "__main__":
    check_and_install()