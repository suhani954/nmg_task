"""Only module allowed to contact Ollama. No prompts or raw responses are logged."""
import json
import time
import httpx
from pydantic import ValidationError
from .config import Config
from .db import session

class BudgetExceeded(Exception):
    pass

class InvalidModelOutput(Exception):
    pass

class Gateway:
    def __init__(self, tenant, ticket_id, run_id, cfg=None):
        self.tenant, self.ticket_id, self.run_id = tenant, ticket_id, run_id
        self.cfg = cfg or Config()

    def _reserve(self, amount):
        with session(self.tenant,self.cfg) as conn:
            # All callers lock run before ticket, avoiding inconsistent lock order.
            run = conn.execute('SELECT * FROM runs WHERE id=%s FOR UPDATE',(self.run_id,)).fetchone()
            ticket = None
            if self.ticket_id:
                ticket = conn.execute('SELECT tokens_reserved FROM tickets WHERE tenant=%s AND id=%s FOR UPDATE',
                                      (self.tenant,self.ticket_id)).fetchone()
            if run['tokens_reserved']+amount > run['token_limit'] or (ticket and ticket['tokens_reserved']+amount > self.cfg.ticket_budget):
                raise BudgetExceeded('token reservation exceeds configured budget')
            conn.execute('UPDATE runs SET tokens_reserved=tokens_reserved+%s WHERE id=%s',(amount,self.run_id))
            if ticket:
                conn.execute('UPDATE tickets SET tokens_reserved=tokens_reserved+%s WHERE tenant=%s AND id=%s',
                             (amount,self.tenant,self.ticket_id))

    def _record(self, task, model, reserved, data, elapsed, error=None):
        ti, to = int(data.get('prompt_eval_count',0)), int(data.get('eval_count',0))
        # Unknown consumption on provider failure retains its reservation.
        charged = ti+to if not error else reserved
        with session(self.tenant,self.cfg) as conn:
            conn.execute('UPDATE runs SET tokens_reserved=tokens_reserved+%s WHERE id=%s',(charged-reserved,self.run_id))
            if self.ticket_id:
                conn.execute('UPDATE tickets SET tokens_reserved=tokens_reserved+%s WHERE tenant=%s AND id=%s',
                             (charged-reserved,self.tenant,self.ticket_id))
            conn.execute('INSERT INTO model_calls(tenant,ticket_id,run_id,task,model,tokens_in,tokens_out,latency_ms,error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                         (self.tenant,self.ticket_id,self.run_id,task,model,ti,to,elapsed,error))

    def _request(self, task, model, payload, input_text):
        # A byte bound plus schema/framing allowance is intentionally conservative.
        allowance = len(input_text.encode('utf-8')) + len(json.dumps(payload.get('format',{})).encode()) + 512
        reserve = allowance + (self.cfg.max_output if task!='embedding' else 0)
        self._reserve(reserve)
        start = time.monotonic()
        try:
            endpoint = '/api/embed' if task=='embedding' else '/api/chat'
            response = httpx.post(self.cfg.ollama_url+endpoint,json=payload,timeout=self.cfg.timeout,trust_env=False)
            response.raise_for_status()
            data = response.json()
            if 'prompt_eval_count' not in data or (task!='embedding' and 'eval_count' not in data):
                raise ValueError('provider omitted token usage')
        except Exception as exc:
            self._record(task,model,reserve,{},int((time.monotonic()-start)*1000),type(exc).__name__)
            raise
        self._record(task,model,reserve,data,int((time.monotonic()-start)*1000))
        if data['prompt_eval_count'] > allowance:
            raise BudgetExceeded('provider exceeded conservative input reservation')
        return data

    def structured(self, task, system, user, contract):
        model = self.cfg.triage_model if task=='triage' else self.cfg.draft_model
        messages = [{'role':'system','content':system},{'role':'user','content':user}]
        for attempt in range(2):
            payload = {'model':model,'stream':False,'messages':messages,'format':contract.model_json_schema(),
                       'options':{'temperature':0,'seed':self.cfg.seed,'num_predict':self.cfg.max_output},'keep_alive':self.cfg.keep_alive}
            data = self._request(task,model,payload,json.dumps(messages,ensure_ascii=False))
            try:
                return contract.model_validate_json(data['message']['content'])
            except (ValidationError,KeyError,TypeError) as exc:
                if attempt:
                    raise InvalidModelOutput('invalid structured output after one repair') from exc
                # Do not echo malformed output back; it might contain leaked or attacker text.
                messages.append({'role':'user','content':'The response did not validate. Return every required field with the exact JSON schema types. No additional fields.'})

    def embed(self, text):
        data = self._request('embedding',self.cfg.embed_model,
                             {'model':self.cfg.embed_model,'input':text,'truncate':False,'keep_alive':self.cfg.keep_alive},text)
        vector = data['embeddings'][0]
        if len(vector)!=768:
            raise ValueError('embedding_dimension_mismatch')
        return vector

    def metrics(self):
        with session(self.tenant,self.cfg) as conn:
            rows = conn.execute('SELECT model,tokens_in,tokens_out FROM model_calls WHERE tenant=%s AND ticket_id=%s',
                                (self.tenant,self.ticket_id)).fetchall()
        return '+'.join(sorted({r['model'] for r in rows})),sum(r['tokens_in'] for r in rows),sum(r['tokens_out'] for r in rows)
