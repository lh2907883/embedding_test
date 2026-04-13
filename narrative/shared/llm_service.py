import json
from openai import OpenAI
from config import DEEPSEEK_API_KEY, LLM_BASE_URL, LLM_MODEL


class LlmService:
    def __init__(self, api_key: str = DEEPSEEK_API_KEY, base_url: str = LLM_BASE_URL, model: str = LLM_MODEL):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def decide(self, system_prompt: str, user_prompt: str) -> dict:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
        content = resp.choices[0].message.content
        return json.loads(content)

    def close(self):
        pass
