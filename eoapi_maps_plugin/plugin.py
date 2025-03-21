from pygeoapi.provider.base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderQueryError,
    ProviderItemNotFoundError,
)
import requests
from urllib.parse import urlparse
import logging


LOGGER = logging.getLogger(__name__)


class EOAPIProvider(BaseProvider):

    FALLBACK_ASSET = "visual"

    def __init__(self, provider_def, *args, **kwargs):
        """Inherit from parent class"""

        super().__init__(provider_def)

    def query(
        self,
        bbox=[],
        datetime_=None,
        width=256,
        height=256,
        format_="png",
        style=None,
        **kwargs,
    ):
        response = requests.get(self.data)
        self._handle_upstream_error(response.text, response.status_code)

        collection = response.json()
        if not style:
            style = "default"

        render_data = self._get_render_data(collection, style)

        eoapi_raster_url = self._get_eoapi_raster_url()
        search_data = {
            "collections": [collection["id"]],
            "bbox": bbox,
            "datetime": datetime_,
        }
        eoapi_search_url = f"{eoapi_raster_url}/searches/register"
        response = requests.post(eoapi_search_url, json=search_data)
        LOGGER.debug(f"POST: {response.url} with {search_data}")
        self._handle_upstream_error(response.text, response.status_code)

        search_id = response.json()["id"]

        eoapi_get_search_template = (
            "{url}/searches/{search_id}/bbox/{bbox}/{width}x{height}.{format}"
        )

        response = requests.get(
            eoapi_get_search_template.format(
                url=eoapi_raster_url,
                search_id=search_id,
                bbox=",".join(map(str, bbox)),
                width=width,
                height=height,
                format=format_,
            ),
            params=render_data,
        )
        LOGGER.debug(f"GET: {response.url}")
        self._handle_upstream_error(response.text, response.status_code)

        return response.content

    def _handle_upstream_error(self, response_text, response_code):
        if response_code < 300:
            return
        if response_code >= 500:
            raise ProviderConnectionError(
                response_text, user_msg="Internal server error"
            )
        if response_code == 404:
            ProviderItemNotFoundError(
                response_text,
                user_msg=f"Item not found",
            )
        if response_code >= 400:
            raise ProviderQueryError(
                response_text, user_msg=f"Bad request: {response_text}"
            )

    def _get_render_data(self, collection: dict, style: str = "default") -> dict:
        if renders := collection.get("renders", {}):
            if not renders.get(style):
                style = next(r for r in collection["renders"].keys())

            assets = collection["renders"][style].get("assets")
            colormap_name = collection["renders"][style].get("colormap_name")
            resampling = collection["renders"][style].get("resampling")
            expression = collection["renders"][style].get("expression")
            render_data = {
                "colormap_name": colormap_name,
                "resampling": resampling,
            }
            if expression:
                render_data["expression"] = expression
                render_data["asset_as_bands"] = "true"
            else:
                render_data["assets"] = assets
        elif collection.get("item_assets", {}).get(self.FALLBACK_ASSET):
            render_data = {"assets": [self.FALLBACK_ASSET]}
        else:
            raise ProviderQueryError(
                "Collection does not have rendering configured.",
                user_msg=(
                    f"""Collection {collection["id"]} does not have rendering enabled. """
                    f"""Ensure the collection has the render extension with a `{style}` """
                    f"""key render, or an asset with the `{self.FALLBACK_ASSET}` key set"""
                    """as fallback"""
                ),
            )

        return render_data

    def _get_eoapi_raster_url(self) -> str:
        url = urlparse(self.data)

        return f"{url.scheme}://{url.netloc}/raster/"
