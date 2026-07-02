import subprocess
import os

def check_and_install():
    print("--- NAVJEEVAN TOOL INSTALLER ---")
    
    # 1. Check Python packages
    print("\n[1/2] Checking Python Dependencies...")
    subprocess.run(["python", "-m", "pip", "install", "subprocess.run", "fastapi", "uvicorn", "sqlalchemy", "google-generativeai"])
    
    # 2. Check System Tools
    print("\n[2/2] Checking System Security Tools...")
    tools = {
        "nmap": "Nmap (Network Scanner)",
        "subfinder": "Subfinder (Subdomain Finder)",
        "nuclei": "Nuclei (Vulnerability Scanner)"
    }

    for cmd, name in tools.items():
        print(f"\nChecking for {name}...")
        try:
            # Check if tool is installed
            subprocess.run([cmd, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print(f"✅ {name} is INSTALLED.")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"❌ {name} is NOT INSTALLED.")
            if cmd == "nmap":
                print("   -> Please download from: https://nmap.org/download.html")
            elif cmd == "subfinder":
                print("   -> Please download from: https://github.com/projectdiscovery/subfinder/releases")
            elif cmd == "nuclei":
                print("   -> Please download from: https://github.com/projectdiscovery/nuclei/releases")

    print("\n--- INSTALLATION CHECK COMPLETE ---")

if __name__ == "__main__":
    check_and_install()