"""
app/api/routes/customers.py
────────────────────────────────────────────────────────────────────────────
Read-only endpoints for browsing synced customer and order data.

GET /customers              — list / search customers
GET /customers/{id}         — single customer profile
GET /customers/{id}/orders  — orders for a customer
GET /orders                 — list / search orders
GET /orders/{id}            — single order with line items
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import CustomerResponse, OrderResponse
from app.database.connection import get_db
from app.models.tables import Customer, Order

router = APIRouter(tags=["Customers & Orders"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Customers
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(
    email: Optional[str] = Query(None, description="Filter by email (partial match)"),
    name: Optional[str] = Query(None, description="Filter by first or last name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    country: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Customer)
    if email:
        q = q.filter(Customer.email.ilike(f"%{email}%"))
    if name:
        q = q.filter(
            (Customer.first_name.ilike(f"%{name}%")) |
            (Customer.last_name.ilike(f"%{name}%"))
        )
    if status:
        q = q.filter(Customer.status == status)
    if country:
        q = q.filter(Customer.country.ilike(f"%{country}%"))
    return q.order_by(Customer.customer_since.desc()).offset(offset).limit(limit).all()


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: UUID, db: Session = Depends(get_db)):
    c = db.query(Customer).filter_by(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@router.get("/customers/{customer_id}/orders", response_model=list[OrderResponse])
def get_customer_orders(
    customer_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    c = db.query(Customer).filter_by(id=customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    orders = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter_by(customer_id=customer_id)
        .order_by(Order.ordered_at.desc())
        .limit(limit)
        .all()
    )
    return orders


# ─────────────────────────────────────────────────────────────────────────────
#  Orders
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/orders", response_model=list[OrderResponse])
def list_orders(
    status: Optional[str] = Query(None),
    customer_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Order).options(joinedload(Order.items))
    if status:
        q = q.filter(Order.status == status)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    return q.order_by(Order.ordered_at.desc()).offset(offset).limit(limit).all()


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: UUID, db: Session = Depends(get_db)):
    order = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter_by(id=order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
