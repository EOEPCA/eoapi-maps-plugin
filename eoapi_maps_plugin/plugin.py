from pygeoapi.provider.base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderQueryError,
)
import requests


class EOAPIProvider(BaseProvider):

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
        search_data = {
            "collections": [self.options["stac_collection"]],
            "bbox": bbox,
            "datetime": datetime_,
        }
        response = requests.post(f"{self.data}/searches/register", json=search_data)

        if response.status_code >= 500:
            raise ProviderConnectionError(response.text)
        elif response.status_code >= 400:
            raise ProviderQueryError(response.text)

        search_id = response.json()["id"]
        render_data = {"assets": self.options["default_asset"]}

        if style:
            render_data["colormap_name"] = style

        eoapi_get_template = (
            "{url}/searches/{search_id}/bbox/{bbox}/{width}x{height}.{format}"
        )

        response = requests.get(
            eoapi_get_template.format(
                url=self.data,
                search_id=search_id,
                bbox=",".join(map(str, bbox)),
                width=width,
                height=height,
                format=format_,
            ),
            params=render_data,
        )

        if response.status_code >= 500:
            raise ProviderConnectionError(response.text)
        elif response.status_code >= 400:
            raise ProviderQueryError(response.text)

        return response.content
