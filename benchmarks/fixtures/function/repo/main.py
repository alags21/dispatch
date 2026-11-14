from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from domain import total, average
from permissions import can_read

app = FastAPI()

class Quote(BaseModel):
    price: float
    quantity: int

@app.post("/quote")
def quote(body: Quote):
    return {"total": total(body.price, body.quantity)}

@app.get("/documents/{document_id}")
def document(document_id: int, user_id: int):
    if not can_read(user_id, 7):
        raise HTTPException(403, "Forbidden")
    return {"id": document_id, "owner_id": 7}

@app.get("/stats")
def stats():
    return {"average": average([])}
