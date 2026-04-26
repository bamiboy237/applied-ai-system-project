"""llm wrapper and agentic loop - calls the model, dispatches tool calls, returns reviews."""

from openai import OpenAI

from codereview.config import get_settings
from codereview.patcher import parse_reviews
from codereview.prompts import get_system_prompt

client = OpenAI(api_key=get_settings().openai_api_key.get_secret_value())


responses = client.responses.create(
    model=get_settings().openai_model,
    instructions=get_system_prompt(),
    input="",
    temperature=0.5,
)

reviews = parse_reviews(responses.output_text)
