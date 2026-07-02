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
            # Multiple Models for different tasks
            self.model_fast = "llama-3.1-8b-instant"      # Planning & Fast tasks
            self.model_smart = "llama-3.3-70b-versatile"  # Analysis & Accuracy
            self.model_deep = "mixtral-8x7b-32768"        # Attack Path & Large Context

    def generate_workflow_plan(self, project_name: str, project_desc: str, assets: list):
        if not self.client: return "AI Not Configured"
        context = f"Project: {project_name}\nDesc: {project_desc}\nAssets: {assets}"
        prompt = f"Act as a Security Planner. Create a workflow plan for:\n{context}"
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=self.model_fast
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
                model=self.model_fast # Using Fast Model
            )
            clean_text = chat_completion.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_text)
            
            valid_tools = ["subfinder", "httpx", "nuclei", "nmap", "katana", "gau", "naabu"]
            if isinstance(parsed, list) and len(parsed) > 0:
                # Always return list[str]
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
                model=self.model_fast # Using Fast Model
            )
            clean_text = chat_completion.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except: return ["admin", "login", "backup"]

    def correlate_findings(self, project_name: str, findings: list):
        if not self.client: return "AI Not Configured."
        try:
            findings_text = "\n".join([f"- {f['tool']}: {f['title']} ({f['severity']})" for f in findings])
            prompt = f"Act as Elite Security Architect. Project: {project_name}\nFindings:\n{findings_text}\n1. Generate Attack Path. 2. Business Impact. 3. Risk Score /100."
            # Using Deep Model for large context and complex reasoning
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_deep
            )
            return chat_completion.choices[0].message.content
        except Exception as e: return f"AI Error: {str(e)}"

    def validate_finding(self, finding: dict, evidence: str):
        if not self.client: return "AI Not Configured."
        try:
            prompt = f"""
            Act as a Senior Application Security Expert.
            Tool: {finding.get('tool')}
            Finding Title: {finding.get('title')}
            Raw Evidence: {evidence}
            
            Analyze this evidence. Is this a True Positive (real bug) or False Positive (scanner mistake/tool error)?
            Reply strictly in this format:
            Verdict: [True Positive / False Positive]
            Reason: [1-2 lines explaining why]
            """
            # Using Smart Model for high accuracy analysis
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_smart
            )
            return chat_completion.choices[0].message.content
        except Exception as e: return f"AI Error: {str(e)}"

    def owasp_audit(self, project_name: str, findings: list):
        if not self.client: return {"error": "AI Not Configured."}
        try:
            findings_text = "\n".join([f"ID: {f['id']} | Title: {f['title']} | Severity: {f['severity']} | Tool: {f['tool']}" for f in findings])
            prompt = f"""
            You are an Expert Security Auditor. 
            Project: {project_name}
            Findings:
            {findings_text}

            Map each finding to the most relevant OWASP Top 10 category (A01 to A10).
            Calculate an overall Risk Score (0-100).
            Identify the top category with the most findings.
            Write a 2-paragraph executive summary (narrative).

            Output STRICTLY in this JSON format without markdown:
            {{
              "owasp_summary": {{"A01-Broken Access Control": [1, 5], "A03-Injection": [2]}},
              "risk_score": 85,
              "top_category": "A03-Injection",
              "narrative": "Paragraph 1... Paragraph 2..."
            }}
            """
            chat_completion = self.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.model_smart # Using Smart Model for accurate categorization
            )
            clean_text = chat_completion.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)
        except Exception as e:
            return {"error": f"AI Audit Error: {str(e)}"}

ai_gateway = AIGateway()