# Sequence Diagrams

This document describes the main workflow of the Second-Hand Clothing App, from a seller publishing a clothing item to a buyer purchasing it. The application consists of a **Client** and four microservices: **Clothing Catalog Service**, **Order Service**, **Payment Service** and **Notification Service** (WebSocket).

The **simple version** provides a high-level overview of the main flow (publish, buy, pay, notify) with the two actors (Buyer and Seller) and the essential steps, without going into technical details.

## Simple version

```mermaid
sequenceDiagram
    autonumber

    actor Buyer
    participant Client
    participant Catalog as Clothing Catalog Service
    participant Order as Order Service
    participant Payment as Payment Service
    participant Notif as Notification Service
    actor Seller

    Seller->>Client: Publish item
    Client->>Catalog: POST /clothes
    Catalog-->>Client: Item published

    Buyer->>Client: Browse catalog
    Client->>Catalog: GET /clothes
    Catalog-->>Client: Available items

    Buyer->>Client: Buy item
    Client->>Order: POST /orders
    Order-->>Client: Order (Pending Payment)

    Client->>Payment: POST /payments

    alt Payment successful
        Payment->>Order: Payment approved (Paid)
        Order->>Catalog: Item purchased (Sold)
        Order->>Notif: Item sold
        Notif--)Seller: WebSocket: item sold
        Notif--)Buyer: WebSocket: favorite item sold/removed (if favorited)
        Payment-->>Client: Payment approved
        Client-->>Buyer: Purchase confirmation
    else Payment failed
        Payment-->>Client: Payment declined
        Client-->>Buyer: Error message
    end
```

The **detailed version** adds, on top of those steps, the implementation details: the WebSocket connection (buyer/seller rooms), the exact publish fields (category, size, condition), search and favorite toggling, 16-digit card validation, the item deletion flow, profile loading (listings, sold items, favorites, history and notifications) and notifications to users who had the item in favorites. In short, the simple version is for understanding the business flow; the detailed version is for understanding how it runs technically.

## Detailed version

```mermaid
sequenceDiagram
    autonumber

    actor User
    participant Client
    participant Catalog as Clothing Catalog Service
    participant Order as Order Service
    participant Payment as Payment Service
    participant Notif as Notification Service

    Note over Client,Notif: The user keeps a single WebSocket connection (buyer + seller rooms)
    Client->>Notif: WebSocket: connect (buyer room + seller room)
    Notif-->>Client: Connection established

    User->>Client: Publish clothing item
    Client->>Catalog: POST /clothes (name, price, seller, category, size, condition)
    Catalog-->>Client: 201 Created (item Available)
    Client-->>User: Listing confirmation

    User->>Client: Open catalog
    Client->>Catalog: GET /clothes?status=Available (or ?q=term)
    Catalog-->>Client: 200 OK (available items)
    Client-->>User: Show catalog

    opt User saves/removes an item to favorites
        User->>Client: Toggle favorite
        Client->>Catalog: POST /favorites (or DELETE /favorites/{user}/{item})
        Catalog-->>Client: 200/201/204
        Client-->>User: Favorite state updated
    end

    User->>Client: Buy item
    Client->>Order: POST /orders
    Order-->>Client: 201 Created (orderId, amount, Pending Payment)

    Client->>Payment: POST /payments (orderId, amount, card details)
    Payment->>Payment: Validate 16-digit card and process

    alt Payment successful
        Payment->>Order: Payment approved
        Note right of Order: Order status: Paid
        Order->>Catalog: Item purchased
        Note right of Catalog: Item status: Sold
        Order->>Notif: Item sold
        par Notify seller and favorites users
            Notif--)User: WebSocket: your item was sold (seller room)
            Notif--)User: WebSocket: favorite item sold/removed (buyer rooms of favorites users)
        end
        Payment-->>Client: 200 OK (paymentId, Approved)
        Client-->>User: Purchase confirmation
        Client->>Client: Reload catalog, favorites, history, listings, notifications
    else Payment failed
        Payment-->>Client: 200 OK (paymentId, Declined)
        Note right of Order: Order stays Pending Payment (hidden from history)
        Client-->>User: Error message
    end

    opt User deletes an item
        User->>Client: Delete item
        Client->>Catalog: DELETE /clothes/{id}
        Catalog->>Catalog: Remove item and its favorites
        Catalog->>Notif: Item deleted (with favorite users)
        Notif--)User: WebSocket: favorite item sold/removed (buyer rooms)
        Catalog-->>Client: 204 No Content
        Client-->>User: Item removed
    end

    User->>Client: Open profile
    Client->>Catalog: GET /clothes?seller={user}
    Client->>Catalog: GET /favorites/{user}
    Client->>Order: GET /orders/buyer/{user}
    Client->>Notif: GET /notifications/user/{user}
    Client-->>User: Show listings, sold items, favorites, purchase history and notifications
```

## Implementation notes

1. **Service-to-service calls are implemented**:
   - Payment Service → Order Service (mark order as paid).
   - Order Service → Clothing Catalog Service (mark item as sold).
   - Order Service → Notification Service (push "item sold").
   - Clothing Catalog Service → Notification Service (push "item deleted" to favorite users).
   - Notification Service → Clothing Catalog Service (fetch users who favorited an item).
2. **Real-time communication** uses Socket.IO with rooms `buyer-<user>` and `seller-<user>`. A single user connection joins both rooms.
3. **Failed payment**: a declined payment is returned as a normal result with status `Declined`; the order stays `Pending Payment`, no item is marked as sold and no notification is sent.
4. **Pending orders are not shown** in the purchase history; only paid orders are displayed.
5. **Notifications are persisted** in MongoDB and can be listed (`GET /notifications/user/{user}`) or deleted individually/all.
6. **Favorites** are managed in the Clothing Catalog Service and are shown inside the Profile tab. Favorite users are notified when their favorited item is sold or deleted.
7. **Item deletion** removes the item and its favorites, then notifies affected favorite users.