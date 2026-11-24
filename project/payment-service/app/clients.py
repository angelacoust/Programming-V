import os

import httpx

ORDER_URL = os.getenv("ORDER_URL", "http://localhost:8002")


class ServiceUnavailable(Exception):
    """Another service could not be reached or answered with an error."""

    def __init__(self, service: str):
        super().__init__(f"{service} service is unavailable")
        self.service = service


async def get_order(order_id: str) -> dict | None:
    """Fetch one order from the Order service."""
    try:
        async with httpx.AsyncClient(base_url=ORDER_URL, timeout=5) as client:
            response = await client.get(f"/orders/{order_id}")
    except httpx.RequestError as error:
        raise ServiceUnavailable("Order") from error
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise ServiceUnavailable("Order")
    return response.json()


async def mark_order_paid(order_id: str) -> int:
    """Tell the Order service that an order has been paid."""
    endpoints = [f"/orders/{order_id}/pay", f"/orders/{order_id}/mark-paid", f"/orders/{order_id}/paid"]
    last_error = None
    for path in endpoints:
        try:
            async with httpx.AsyncClient(base_url=ORDER_URL, timeout=5) as client:
                response = await client.post(path)
            if response.status_code in (200, 201, 204):
                return 1
        except httpx.HTTPError as error:
            last_error = error
            continue
    # Fallback to PATCH.
    try:
        async with httpx.AsyncClient(base_url=ORDER_URL, timeout=5) as client:
            response = await client.patch(f"/orders/{order_id}", json={"paid": True, "status": "Paid"})
        if response.status_code in (200, 201, 204):
            return 1
    except httpx.HTTPError as error:
        last_error = error
    if last_error:
        raise ServiceUnavailable("Order") from last_error
    return 0
