import requests
import argparse
import logging
from requests.adapters import HTTPAdapter, Retry

LOGGER = logging.getLogger("pygeoapi-stacapi-sync")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(name)-12s] %(levelname)-8s %(message)s")
handler.setFormatter(formatter)
LOGGER.addHandler(handler)

SESSION = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
SESSION.mount("http://", HTTPAdapter(max_retries=retries))
RENDER_EXTENSION_NAME = "renders"
VISUAL_ASSET_NAME = "visual"


def get_stacapi_pygeoapi_diff(
    collection: dict, pygeoapi_resource: dict, collection_id: str
) -> dict:
    diff = {}
    if collection["id"] != collection_id:
        diff["id"] = collection["id"]
        LOGGER.debug(
            f"Collection id changed from {collection_id} to {collection['id']}"
        )

    if collection["description"] != pygeoapi_resource["description"]:
        diff["description"] = collection["description"]
        LOGGER.debug(f"Description updated")

    stacapi_bbox = collection["extent"]["spatial"]["bbox"][0]
    pygeoapi_bbox = pygeoapi_resource["extents"]["spatial"]["bbox"]
    if stacapi_bbox != pygeoapi_bbox:
        if not diff.get("extent"):
            diff["extent"] = {}
        diff["extent"]["spatial"] = collection["extent"]["spatial"]
        LOGGER.debug(f"Bbox updated from {pygeoapi_bbox} to {stacapi_bbox}")

    stacapi_interval = collection["extent"]["temporal"]["interval"][0]
    pygeoapi_begin = (
        pygeoapi_resource.get("extents", {}).get("temporal", {}).get("begin")
    )
    pygeoapi_end = pygeoapi_resource.get("extents", {}).get("temporal", {}).get("end")
    pygeoapi_interval = [pygeoapi_begin, pygeoapi_end]
    if stacapi_interval != pygeoapi_interval:
        if not diff.get("extent"):
            diff["extent"] = {}
        diff["extent"]["temporal"] = collection["extent"]["temporal"]
        LOGGER.debug(
            f"Temporal interval updated from {pygeoapi_interval} to {stacapi_interval}"
        )

    if collection.get("keywords", []) != pygeoapi_resource["keywords"]:
        diff["keywords"] = collection["keywords"]
        LOGGER.debug(
            f"Keywords updated from {pygeoapi_resource['keywords']} to {collection['keywords']}"
        )

    if collection["title"] != pygeoapi_resource["title"]:
        diff["title"] = collection["title"]
        LOGGER.debug(
            f"Title updated from {pygeoapi_resource['title']} to {collection['title']}"
        )

    return diff


def validate_links(links: list[dict], extract_missing_mimetypes: bool) -> list[dict]:
    validated_links = []
    for link in links:
        if not link.get("type"):
            if extract_missing_mimetypes:
                r = SESSION.get(link["href"])
                if r.status_code >= 400:
                    LOGGER.error(
                        f"Failed to extract mimetype for link {link['href']}, status code {r.status_code}, defaulting to application/octet-stream"
                    )
                    link["type"] = "application/octet-stream"
                    continue
                mimetype = r.headers.get("Content-Type", "application/octet-stream")
                link["type"] = mimetype
            else:
                link["type"] = "application/octet-stream"

        if not link.get("title"):
            link["title"] = ""

        validated_links.append(link)

    return validated_links


def is_renderable(collection: dict) -> bool:
    return collection.get(RENDER_EXTENSION_NAME) or collection.get(
        "item_assets", {}
    ).get(VISUAL_ASSET_NAME, False)


def get_data(eoapi_url: str, pygeoapi_resource_url: str) -> tuple[dict, dict]:
    # get collections from STAC API
    r = SESSION.get(f"{eoapi_url}/stac/collections")
    r.raise_for_status()
    stac_collections = r.json()

    # get resources from pygeoapi
    r = SESSION.get(pygeoapi_resource_url)
    r.raise_for_status()
    pygeoapi_resources = r.json()

    return stac_collections, pygeoapi_resources


def main():
    LOGGER.info("Starting pygeoapi-stacapi-sync")
    parser = argparse.ArgumentParser(
        prog="pygeoapi-stacapi-sync",
        description="Syncs STAC API collections with pygeoapi resources",
    )

    parser.add_argument("eoapi_url")
    parser.add_argument("pygeoapi_url")
    parser.add_argument(
        "-c",
        "--create",
        action="store_true",
        help="Create collections in pygeoapi that are present in STAC API",
    )
    parser.add_argument(
        "-d",
        "--delete",
        action="store_true",
        help="Delete collections from pygeoapi that aren't present in STAC API",
    )
    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        help="Update metadata in pygeoapi to match STAC API",
    )
    parser.add_argument(
        "-l",
        "--extract-missing-mimetypes",
        action="store_true",
        help="Extract mimetypes for missing links",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Set log level to debug",
    )

    args = parser.parse_args()

    eoapi_url = args.eoapi_url
    pygeoapi_url = args.pygeoapi_url
    create = args.create
    delete = args.delete
    update = args.update
    extract_missing_mimetypes = args.extract_missing_mimetypes
    debug = args.debug

    if debug:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.INFO)

    pygeoapi_resource_url = f"{pygeoapi_url}/admin/config/resources"

    # add collections to STAC API that aren't present as pygeoapi resources that
    # have the render extension or visual asset
    if create:
        stac_collections, pygeoapi_resources = get_data(
            eoapi_url, pygeoapi_resource_url
        )
        for collection in stac_collections["collections"]:
            is_pygeoapi_resource = pygeoapi_resources.get(collection["id"], False)
            if not is_pygeoapi_resource and is_renderable(collection):
                LOGGER.info(f"Creating collection {collection['id']} in pygeoapi")

                description = collection.get("description", "")
                keywords = collection.get("keywords", [])
                links = validate_links(
                    collection.get("links", []), extract_missing_mimetypes
                )
                collection_id = collection["id"]
                title = collection["title"]

                # TODO: handle multiple bboxes if relevant
                bbox = collection["extent"]["spatial"]["bbox"][0]

                begin_datetime = collection["extent"]["temporal"]["interval"][0][0]
                end_datetime = collection["extent"]["temporal"]["interval"][0][1]

                data_url = f"{eoapi_url}/stac/collections/{collection_id}"

                json = {
                    collection["id"]: {
                        "description": description,
                        "extents": {
                            "spatial": {
                                "bbox": bbox,
                                "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                            },
                            "temporal": {"begin": begin_datetime, "end": end_datetime},
                        },
                        "keywords": keywords,
                        "links": links,
                        "providers": [
                            {
                                "data": data_url,
                                "format": {
                                    "mimetype": "image/png",
                                    "name": "png",
                                },
                                "name": "eoapi_maps_plugin.EOAPIProvider",
                                "type": "map",
                            }
                        ],
                        "title": title,
                        "type": "collection",
                    }
                }

                r = SESSION.post(pygeoapi_resource_url, json=json)
                if r.status_code >= 400:
                    LOGGER.error(
                        f"Failed to create collection {collection['id']} in pygeoapi. Status code {r.status_code}. Response: {r.text}"
                    )

    # remove data from pygeoapi not in STAC API or that don't have the render
    # extension or visual asset
    if delete:
        stac_collections, pygeoapi_resources = get_data(
            eoapi_url, pygeoapi_resource_url
        )
        collection_ids = [
            collection["id"] for collection in stac_collections["collections"]
        ]

        collections_to_delete = []
        for id, resource in pygeoapi_resources.items():
            if id not in collection_ids:
                collections_to_delete.append(id)
            elif not is_renderable(
                next(filter(lambda x: x["id"] == id, stac_collections["collections"]))
            ):
                collections_to_delete.append(id)

        for id in collections_to_delete:
            LOGGER.info(f"Deleting collection {id} from pygeoapi")
            r = SESSION.delete(f"{pygeoapi_resource_url}/{id}")
            if r.status_code >= 400:
                LOGGER.error(
                    f"Failed to delete collection {collection['id']} in pygeoapi. Status code {r.status_code}. Response: {r.text}"
                )

    # update metadata in pygeoapi to match STAC API (eg. changed extent, description...)
    if update:
        stac_collections, pygeoapi_resources = get_data(
            eoapi_url, pygeoapi_resource_url
        )
        for collection in stac_collections["collections"]:
            is_pygeoapi_resource = pygeoapi_resources.get(collection["id"], False)
            if is_pygeoapi_resource and is_renderable(collection):
                resource = pygeoapi_resources.get(collection["id"])
                if not resource:
                    LOGGER.info(
                        f"Collection {collection['id']} not found in pygeoapi, will be created at next cycle"
                    )
                    continue
                diff = get_stacapi_pygeoapi_diff(collection, resource, collection["id"])

                if diff:
                    LOGGER.info(f"Updating collection {collection['id']} in pygeoapi")
                    r = SESSION.patch(
                        f"{pygeoapi_resource_url}/{collection['id']}",
                        json=diff,
                    )
                    if r.status_code >= 400:
                        LOGGER.error(
                            f"Failed to update collection {collection['id']} in pygeoapi. Status code {r.status_code}. Response: {r.text}"
                        )

    LOGGER.info("pygeoapi-stacapi-sync finished")


if __name__ == "__main__":
    main()
