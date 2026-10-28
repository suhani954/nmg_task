from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Category = Literal['returns_refunds','shipping_delivery','warranty_repair','order_change','billing_payments','assembly_setup','appointments','records_privacy','clinical','other']
Priority = Literal['urgent','high','normal','low']
Action = Literal['draft_reply','ask_for_info','escalate']

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Ticket(Contract):
    id: str = Field(min_length=1, max_length=200)
    tenant: Literal['northwind','harbor']
    customer_ref: str
    subject: str = Field(max_length=2000)
    body: str = Field(max_length=30000)
    received_at: datetime

class TriageResult(Contract):
    category: Category
    priority: Priority
    action: Action
    injection_detected: bool
    reason: str = Field(max_length=600)
    missing_details: list[str]

class Passage(Contract):
    kb_id: str
    text: str
    score: float

class DraftResult(Contract):
    text: str = Field(max_length=2500)
    kb_refs: list[str]

class DecisionRecord(Contract):
    ticket_id: str
    tenant: str
    run_id: str
    category: Category
    priority: Priority
    action: Action
    injection_detected: bool
    kb_refs: list[str]
    draft_reply: str | None
    status: Literal['pending_approval','escalated','held_budget','failed']
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
