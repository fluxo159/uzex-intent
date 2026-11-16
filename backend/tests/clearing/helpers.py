import datetime as dt

from app.clearing.models import Ask, Basket, Bid

T0 = dt.datetime(2026, 11, 8, 10, 0)

def bid(mid, q, p, region="R", minute=0):
    return Bid(mandate_id=mid, qty_t=q, max_price_t=p, region=region, created_at=T0 + dt.timedelta(minutes=minute))

def ask(oid, q, p, region="R", lot=1, minute=0):
    return Ask(offer_id=oid, seller=f"S-{oid}", qty_t=q, min_price_t=p, warehouse_region=region, min_lot_t=lot,
               created_at=T0 + dt.timedelta(minutes=minute))

def book(bids=(), asks=()):
    return Basket(basket_id="B-test", bids=list(bids), asks=list(asks))

def got(res, mid):
    return sum(a.qty_t for a in res.allocations if a.mandate_id == mid)
