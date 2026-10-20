
import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
EMBEDDING_DEPLOYMENT = "text-embedding-3-small"

credential = DefaultAzureCredential()

token_provider = get_bearer_token_provider(
    credential,
    "https://cognitiveservices.azure.com/.default",
)

client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    azure_ad_token_provider=token_provider,
    api_version="2024-10-21",
)


def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text")

    response = client.embeddings.create(
        model=EMBEDDING_DEPLOYMENT,
        input=text,
    )

    vector = response.data[0].embedding

    if len(vector) != 1536:
        raise ValueError(
            f"Unexpected embedding dimensions: {len(vector)}"
        )

    return vector


if __name__ == "__main__":
    vector = generate_embedding(
        "The synthetic Q4 revenue forecast is £42 million."
    )

    print("Embedding generated successfully")
    print("Dimensions:", len(vector))
    print("First five values:", vector[:5])
