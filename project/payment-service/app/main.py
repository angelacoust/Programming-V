from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.clients import ServiceUnavailable, get_order, mark_order_paid
from app.db import payments
from app.models import Payment, PaymentCreate


app = FastAPI(title="Payment service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_payment(doc: dict) -> Payment:
    pid = str(doc["_id"])
    order_id = doc.get("order_id")
    amount = doc.get("amount", 0)
    return Payment(
        id=pid,
        paymentId=pid,
        orderId=order_id,
        order_id=order_id,
        amount=amount,
        total=amount,
        status=doc.get("status", "Approved" if doc.get("paid") else "Declined"),
        paid=doc.get("paid", False),
        card_last4=doc.get("card_last4"),
        created_at=doc.get("created_at"),
    )


def normalize_create(body: PaymentCreate) -> dict:
    order_id = body.orderId or body.order_id or body.id or body.order
    # Also search extra fields.
    if not order_id:
        for key, value in (body.model_extra or {}).items():
            if "order" in key.lower() or key.lower() in ("id",):
                if value:
                    order_id = value
                    break
    amount = body.amount if body.amount is not None else (body.total if body.total is not None else body.price)
    if amount is None:
        for key, value in (body.model_extra or {}).items():
            if "amount" in key.lower() or "total" in key.lower() or "price" in key.lower():
                if value is not None:
                    amount = value
                    break
    card_number = body.card_number or body.cardNumber or body.card
    if not card_number:
        for key, value in (body.model_extra or {}).items():
            if "card" in key.lower() or "number" in key.lower():
                if value is not None:
                    card_number = value
                    break
    cvv = body.cvv
    if cvv is None:
        for key, value in (body.model_extra or {}).items():
            if "cvv" in key.lower() or "cvc" in key.lower():
                if value is not None:
                    cvv = value
                    break

    if not order_id:
        raise HTTPException(status_code=400, detail="orderId is required")
    if amount is None:
        # Try to fetch from order.
        amount = None
    try:
        amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount must be a number")

    return {
        "order_id": str(order_id),
        "amount": amount,
        "card_number": str(card_number) if card_number is not None else None,
        "cvv": str(cvv) if cvv is not None else None,
    }


def is_approved(card_number: str | None, cvv: str | None) -> bool:
    if card_number:
        cn = card_number.replace(" ", "")
        if cn.endswith("0000") or "decline" in cn.lower():
            return False
    if cvv and (cvv == "000" or "decline" in str(cvv).lower()):
        return False
    return True


@app.post("/payments", response_model=Payment, status_code=200)
async def create_payment(body: PaymentCreate):
    data = normalize_create(body)
    order_id = data["order_id"]

    # Fetch order to get amount if not provided.
    order = None
    try:
        order = await get_order(order_id)
    except ServiceUnavailable:
        order = None
    amount = data["amount"]
    if amount is None and order is not None:
        amount = order.get("amount") or order.get("total") or order.get("price")
    if amount is None:
        amount = 0.0
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="amount must be a number")

    approved = is_approved(data["card_number"], data["cvv"])

    card_last4 = None
    if data["card_number"]:
        digits = "".join(ch for ch in data["card_number"] if ch.isdigit())
        if digits:
            card_last4 = digits[-4:]

    now = datetime.now(timezone.utc)
    created_at = now.replace(microsecond=now.microsecond // 1000 * 1000)
    doc = {
        "order_id": order_id,
        "amount": amount,
        "paid": approved,
        "status": "Approved" if approved else "Declined",
        "card_last4": card_last4,
        "created_at": created_at,
    }
    result = await payments.insert_one(doc)
    doc["_id"] = result.inserted_id

    if approved:
        try:
            await mark_order_paid(order_id)
        except ServiceUnavailable:
            pass

    return to_payment(doc)


@app.get("/payments/{payment_id}", response_model=Payment)
async def get_payment(payment_id: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        oid = ObjectId(payment_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Payment not found")
    doc = await payments.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return to_payment(doc)


@app.get("/payments", response_model=list[Payment])
async def list_payments(order_id: str | None = None, orderId: str | None = None):
    query = {}
    oid = order_id or orderId
    if oid:
        query["order_id"] = oid
    docs = await payments.find(query).sort([("created_at", -1), ("_id", -1)]).to_list()
    return [to_payment(doc) for doc in docs]
