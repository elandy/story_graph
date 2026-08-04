import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PROVIDER = os.getenv("STORY_GRAPH_LLM_PROVIDER", "google")
DEFAULT_MODEL = os.getenv("STORY_GRAPH_LLM_MODEL", "gemini-3.1-flash-lite")

def _get_chat_llm(
    *,
    api_key: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
):
    provider = provider or DEFAULT_PROVIDER
    model_name = model_name or DEFAULT_MODEL

    if provider == "google":
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0,
        )

    if provider == "openai":
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=0,
        )

    raise ValueError(f"Unsupported provider '{provider}'")