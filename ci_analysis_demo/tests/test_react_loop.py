"""
手动react loop
"""
import json
import os
import string

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def test_react_loop(ci_err: string):
    """"""
    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_API_URL"),
        timeout=int(os.getenv("LLM_TIMEOUT_SECONDS"))
    )
    max_tries = 4
    prompt = f"Error: {ci_err}"
    for i in range(max_tries):
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=[
                {
                    "role": "system", "content": "你是一个CI分析助手"
                },
                {
                    "role": "user", "content": prompt
                }
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        content = resp.choices[0].message.content
        if not content:
            raise Exception("LLM returned empty content")
        print(content)
        # parsed = json.loads(content)
        if i < 3:
            prompt += "\n"
            prompt += f"第{i + 1}次回答：{content}; 请根据此次回答判断是否符合答案，不符合继续往下执行"
        else:
            break
        return content


if __name__ == '__main__':
    ci_error = "ModuleNotFoundError: No module named requests"
    test_react_loop(ci_error)
