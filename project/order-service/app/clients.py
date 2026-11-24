import os

import httpx

CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8001")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8004")


class ServiceUnavailable(Exception):
    """Another service could not be reached or answered with an error."""

    def __init__(self, service: str):
        super().__init__(f"{service} service is unavailable")
        self.service = service


async def mark_item_sold(item_id: str) -> None:
    """Tell the Clothing Catalog service that an item has been sold."""
    endpoints = [
        f"/clothes/{item_id}/sold",
        f"/clothes/{item_id}/purchase",
        f"/clothes/{item_id}/mark-sold",
    ]
    last_error = None
    for path in endpoints:
        try:
            async with httpx.AsyncClient(base_url=CATALOG_URL, timeout=5) as client:
                response = await client.post(path)
            if response.status_code in (200, 201, 204):
                return
            # Try a PATCH status update as a fallback
            async with httpx.AsyncClient(base_url=CATALOG_URL, timeout=5) as client:
                response = await client.patch(path.replace("/sold", "/status").replace("/purchase", "/status").replace("/mark-sold", "/status"), json={"status": "Sold"})
            if response.status_code in (200, 201, 204):
                return
        except httpx.HTTPError as error:
            last_error = error
            continue
    if last_error:
        raise ServiceUnavailable("Catalog") from last_error


async def notify_item_sold(buyer: str, seller: str, item_id: str, item_name: str | None, order_id: str, amount: float | None) -> None:
    """Tell the Notification service to push the 'item sold' event."""
    payload = {
        "buyer": buyer,
        "seller": seller,
        "item_id": item_id,
        "itemId": item_id,
        "item_name": item_name,
        "itemName": item_name,
        "order_id": order_id,
        "orderId": order_id,
        "amount": amount,
    }
    paths = [
        "/notifications/item-sold",
        "/notifications",
        "/notify",
        "/sold",
        "/item-sold",
    ]
    last_error = None
    for path in paths:
        try:
            async with httpx.AsyncClient(base_url=NOTIFICATION_URL, timeout=5) as client:
                response = await client.post(path, json=payload)
            if response.status_code in (200, 201, 202, 204):
                return
        except httpx.HTTPError as error:
            last_error = error
            continue
    if last_error:
        raise ServiceUnavailable("Notification") from last_error
