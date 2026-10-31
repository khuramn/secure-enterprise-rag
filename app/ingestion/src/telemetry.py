import os

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk.resources import Resource


def configure_telemetry():
    connection_string = os.getenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING"
    )

    if not connection_string:
        return False

    configure_azure_monitor(
        connection_string=connection_string,
        resource=Resource.create({
            "service.name": "secure-enterprise-rag-api",
            "deployment.environment.name": "dev",
        }),
        enable_live_metrics=False,
        enable_performance_counters=False,
        disable_offline_storage=True,
        logger_name="secure_rag.azure_audit",
        instrumentation_options={
            "azure_sdk": {"enabled": False},
            "django": {"enabled": False},
            "fastapi": {"enabled": False},
            "flask": {"enabled": False},
            "psycopg2": {"enabled": False},
            "requests": {"enabled": False},
            "urllib": {"enabled": False},
            "urllib3": {"enabled": False},
        },
    )

    return True
