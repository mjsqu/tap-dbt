"""Base class for connecting to th dbt Cloud API."""

from __future__ import annotations

import typing as t
from abc import abstractmethod
from functools import lru_cache

import requests
import yaml
from singer_sdk import RESTStream, GraphQLStream
from singer_sdk._singerlib import resolve_schema_references
from singer_sdk.authenticators import APIAuthenticatorBase, SimpleAuthenticator

OPENAPI_URL = (
    "https://raw.githubusercontent.com/fishtown-analytics/dbt-cloud-openapi-spec"
    "/ee64f573d79585f12d30eaafc223dc8a84052c9a/openapi-v2-old.yaml"
)


@lru_cache(maxsize=None)
def load_openapi() -> dict[str, t.Any]:
    """Load the OpenAPI specification from the package.

    Returns:
        The OpenAPI specification as a dict.
    """
    response = requests.get(OPENAPI_URL, timeout=10)
    return yaml.safe_load(response.text)


class DBTStream(RESTStream):
    """dbt stream class."""

    primary_keys: t.ClassVar[list[str]] = ["id"]
    records_jsonpath = "$.data[*]"

    @property
    def url_base(self) -> str:
        """Base URL for this stream."""
        return f"""{self.config.get("base_url", "https://cloud.getdbt.com/api/v2")}/api/v2"""

    @property
    def http_headers(self) -> dict:
        """HTTP headers for this stream."""
        headers = super().http_headers
        headers["Accept"] = "application/json"
        return headers

    @property
    def authenticator(self) -> APIAuthenticatorBase:
        """Return the authenticator for this stream."""
        return SimpleAuthenticator(
            stream=self,
            auth_headers={
                "Authorization": f"Token {self.config.get('api_key')}",
            },
        )

    def _resolve_openapi_ref(self) -> dict[str, t.Any]:
        schema = {"$ref": f"#/components/schemas/{self.openapi_ref}"}
        openapi = load_openapi()
        schema["components"] = openapi["components"]
        return resolve_schema_references(schema)

    @property
    @lru_cache(maxsize=None)  # noqa: B019
    def schema(self) -> dict[str, t.Any]:
        """Return the schema for this stream.

        Returns:
            The schema for this stream.
        """
        openapi_response = self._resolve_openapi_ref()

        for property_schema in openapi_response["properties"].values():
            if property_schema.get("nullable"):
                if isinstance(property_schema["type"], list):
                    property_schema["type"].append("null")
                else:
                    property_schema["type"] = [property_schema["type"], "null"]

        return openapi_response

    @property
    @abstractmethod
    def openapi_ref(self) -> str:
        """Return the OpenAPI component name for this stream.

        Returns:
            The OpenAPI reference for this stream.
        """
        ...


class DBTDiscoveryStream(GraphQLStream, DBTStream):
    @property
    def url_base(self) -> str:
        """Base URL for this stream."""
        base_url = self.config.get("base_url", "https://cloud.getdbt.com")
        graphql_url = f"""{base_url.replace("https://","https://metadata.")}/graphql"""
        return graphql_url
  
