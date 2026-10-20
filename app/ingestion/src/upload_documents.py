import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT"]

DOCUMENT_PATH = (
    Path(__file__).resolve().parent.parent / "documents"
)


def main():
    credential = DefaultAzureCredential()

    account_url = (
        f"https://{STORAGE_ACCOUNT}.blob.core.windows.net"
    )

    blob_service = BlobServiceClient(
        account_url=account_url,
        credential=credential,
    )

    container = blob_service.get_container_client("documents")

    for file_path in DOCUMENT_PATH.glob("*.md"):
        print(f"Uploading {file_path.name}")

        blob = container.get_blob_client(file_path.name)

        with open(file_path, "rb") as data:
            blob.upload_blob(
                data,
                overwrite=True,
            )

    print("Upload complete.")


if __name__ == "__main__":
    main()