# Second-Hand Clothing App

This repository tracks homework, the individual project, and presentations in one place. This is where the instructor will find verifiable results and submitted versions, and where I can later review how my work progressed.

---
name: Ángela Costa Trigo
neptun: IE2DPE
---

Microservices application for publishing and buying second-hand clothing items. Sellers publish clothing items, buyers browse the catalog, save favorites, purchase items and pay. On successful payment the item is marked as sold and both buyer and seller are notified in real time over WebSocket.

The runnable application lives in [`project/`](project/); the documentation lives in [`docs/`](docs/).

## Services

| Service | Folder | Port | What it does |
|---|---|---|---|
| Clothing Catalog | `project/clothing-catalog-service/` | 8001 | Clothing items and favorites |
| Order | `project/order-service/` | 8002 | Orders and purchase history |
| Payment | `project/payment-service/` | 8003 | Simulated payments |
| Notification | `project/notification-service/` | 8004 | Stored notifications + WebSocket push |
| Client | `project/client/` | 8123 | Web client (HTML + CSS + JS, nginx) |
| MongoDB | (container) | 27017 | One database per service |

## Prerequisites

- Docker Desktop or OrbStack installed and running
- Ports `8123`, `8001`–`8004` and `27017` free

## Running

From the repository root:

```bash
cd project
docker compose up --build
```

Then open the client at http://localhost:8123.

To run it in the background instead, use `docker compose up --build -d`. To stop it, press `Ctrl+C` (attached mode) or run `docker compose down`. Databases start empty on a fresh machine; the local data lives in the Docker volume `mongo-data`, which is not part of the repository.

## Tests

Each service has its own tests. They need MongoDB running on `localhost:27017`; from `project/` run `docker compose up -d mongo` first. Then, for each service:

```bash
cd project/clothing-catalog-service  # or order-service, payment-service, notification-service
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
```

## Client features

- One account can both buy and sell; a single Socket.IO connection joins the buyer and seller rooms.
- Catalog, favorites and purchase history load immediately on page load.
- Favorites can be added **and removed** directly from the UI and turn red instantly.
- Buying opens a dedicated checkout modal with order summary and a card field that must contain exactly 16 digits; payment is explicit instead of automatic.
- Notifications are stored in MongoDB, appear after switching accounts, can be deleted individually or all at once, and only cover sold/removed favorite items and sold items.
- The Profile tab contains listings, sold items, favorites, paid purchase history and notifications.

## Documentation

- [Architecture](docs/architecture.md)
- [Sequence diagrams](docs/sequence-diagrams.md)

## API summary

- Catalog: `POST /clothes`, `GET /clothes`, `GET /clothes/{id}`, `DELETE /clothes/{id}`, `POST /favorites`, `GET /favorites/{user}`
- Order: `POST /orders`, `GET /orders/buyer/{buyerName}`, `GET /orders/{id}`, `POST /orders/{id}/pay`
- Payment: `POST /payments`, `GET /payments/{id}`
- Notification: `GET /notifications/user/{user}`, `DELETE /notifications/{id}`, `DELETE /notifications/user/{user}`, and Socket.IO (rooms `buyer-<user>` and `seller-<user>`)
