import json
import anthropic
from config import ANTHROPIC_API_KEY, LLM_MODEL


class LlmService:
    def __init__(self, api_key: str = ANTHROPIC_API_KEY, model: str = LLM_MODEL):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def decide(self, system_prompt: str, user_prompt: str) -> dict:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.8,
        )
        content = resp.content[0].text
        # 提取 JSON（处理可能的 markdown 包裹）
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content.strip())

    def close(self):
        pass
