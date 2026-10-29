
import os

from azure.identity import (
    DefaultAzureCredential,
    get_bearer_token_provider,
)
from openai import AzureOpenAI


CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "rag-chat-mini")


def get_chat_client():
    credential = DefaultAzureCredential()

    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )

    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )


def generate_answer(question: str) -> str:
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    client = get_chat_client()

    response = client.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an enterprise AI assistant. "
                    "Provide clear, accurate, concise answers. "
                    "Do not invent facts."
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
        temperature=0,
        max_tokens=300,
    )

    answer = response.choices[0].message.content

    if not answer:
        raise RuntimeError("The model returned an empty answer")

    return answer


if __name__ == "__main__":
    question = "What is retrieval-augmented generation?"

    print(f"\nQuestion: {question}")

    answer = generate_answer(question)

    print(f"\nLLM Answer:\n{answer}")
