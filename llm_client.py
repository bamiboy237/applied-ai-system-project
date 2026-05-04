import os


class MockClient:
    """
    Offline stand-in for an LLM client.
    This lets the app run without an API key.
    """

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # Very small, predictable behavior for demos.
        if "Return ONLY valid JSON" in system_prompt:
            # Purposely not JSON to force fallback unless students change behavior.
            return "I found some issues, but I'm not returning JSON right now."
        # Empty output tells the agent to use its deterministic fallback fixer.
        return ""


class OpenAIClient:
    """
    Minimal OpenAI Responses API wrapper.

    Requirements:
    - openai installed
    - OPENAI_API_KEY set in environment (or loaded via python-dotenv)
    """

    def __init__(self, model_name: str = "gpt-5.4-mini", temperature: float = 0.2):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "Missing OPENAI_API_KEY. Create a .env file and set OPENAI_API_KEY=..."
            )

        # Import here so heuristic mode does not require the dependency at import time.
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name
        self.temperature = float(temperature)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a single request to OpenAI and return text output."""
        response = self.client.responses.create(
            model=self.model_name,
            instructions=system_prompt,
            input=user_prompt,
            temperature=self.temperature,
        )
        return response.output_text or ""
