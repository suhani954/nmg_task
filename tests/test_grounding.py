from relay.agents import draft
from relay.contracts import Ticket,TriageResult,DraftResult,Passage

class UnreliableDrafter:
    def structured(self,*args):
        return DraftResult(text='We have refunded INR 9000 and require original packaging.',kb_refs=['NW-KB-01'])

def test_factual_renderer_discards_invented_model_claims():
    ticket=Ticket(id='new-id',tenant='northwind',customer_ref='C-4',subject='Return',body='Unused helmet',received_at='2026-10-28T10:00:00Z')
    result=TriageResult(category='returns_refunds',priority='normal',action='draft_reply',injection_detected=False,reason='return',missing_details=[])
    passages=[Passage(kb_id='NW-KB-01',text='Returns: Unused items can be returned within 30 days with the original invoice.',score=.9)]
    answer=draft(ticket,result,passages,UnreliableDrafter())
    assert 'refunded' not in answer.text
    assert 'packaging' not in answer.text
    assert 'Unused items can be returned within 30 days with the original invoice.' in answer.text
    assert answer.kb_refs==['NW-KB-01']
