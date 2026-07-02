import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

class AIGateway:
    def __init__(self):
        if not GROQ_API_KEY or GROQ_API_KEY == "gsk_your_groq_api_key_here":
            self.client = None
            print("Warning: GROQ_API_KEY Not Configured in .env")
        else:
            self.client = Groq(api_key=GROQ_API_KEY)

    def generate_workflow_plan(self, project_name: str, project_desc: str, assets: list):
        if not self.client: return "AI Not Configured"
        context = f"Project: {project_name}\nDesc: {project_desc}\nAssets: {assets}"
        prompt = f"Act as a Security Planner. Create a workflow plan for:\n{context}"
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192"
        )
        return chat_completion.choices[0].message.content

    def get_autonomous_plan(self, project_name: str, target: str):
        if not self.client: return ["subfinder", "httpx", "nuclei"]
        try:
            prompt = f"""
            You are an autonomous security planner. Target: {target}
            Select 3 tools from ["subfinder", "httpx", "nuclei", "nmap", "katana", "gau"].
            Output STRICTLY JSON array of strings. No markdown.
            Example: ["subfinder", "httpx", "nuclei"]
            """
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192"
            )
            clean_text = chat_completion.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_text)
            
            valid_tools = ["subfinder", "httpx", "nuclei", "nmap", "katana", "gau", "naabu"]
            if isinstance(parsed, list) and len(parsed) > 0:
                if isinstance(parsed[0], dict):
                    return [item.get("tool") for item in parsed if item.get("tool") in valid_tools][:3]
                else:
                    return [t for t in parsed if t in valid_tools][:3]
            return ["subfinder", "httpx", "nuclei"]
        except Exception as e:
            print(f"AI Decision Error: {e}. Using default plan.")
            return ["subfinder", "httpx", "nuclei"]

    def generate_wordlist(self, target: str):
        if not self.client: return ["admin", "login", "api", "config"]
        try:
            prompt = f"Analyze target '{target}'. Generate 20 likely hidden directory names. Output strictly as JSON array of strings."
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-8b-8192"
            )
            clean_text = chat_completion.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except: return ["admin", "login", "backup"]

    def correlate_findings(self, project_name: str, findings: list):
        if not self.client: return "AI Not Configured."
        try:
            findings_text = "\n".join([f"- {f['tool']}: {f['title']} ({f['severity']})" for f in findings])
            prompt = f"Act as Elite Security Architect. Project: {project_name}\nFindings:\n{findings_text}\n1. Generate Attack Path. 2. Business Impact. 3. Risk Score /100."
            # Using 70b model for deep reasoning
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-70b-8192"
            )
            return chat_completion.choices[0].message.content
        except Exception as e: return f"AI Error: {str(e)}"

ai_gateway = AIGateway()