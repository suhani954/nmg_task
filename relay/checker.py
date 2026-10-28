"""Deterministic defense in depth. No model is called from this module."""
import re
import unicodedata
from .db import session

def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())

def check(ticket, draft, passages, articles, forbidden_articles=()):
    reasons=[]
    text=draft.text
    norm=normalized(text)
    public={a['id']:a for a in articles if not a['internal']}
    retrieved={p.kb_id for p in passages}
    cited=set(draft.kb_refs)
    inline=set(re.findall(r'\b(?:NW|HD)-KB-\d+\b',text,re.I))
    if not text.strip(): reasons.append('empty_draft')
    if len(text.split())>150: reasons.append('word_limit')
    if cited != inline: reasons.append('citation_mismatch')
    if not cited.issubset(public) or not cited.issubset(retrieved): reasons.append('invalid_citation')
    for article in list(articles)+list(forbidden_articles):
        if article['internal'] or article in forbidden_articles:
            if normalized(article['id']) in norm: reasons.append('forbidden_reference')
            # Match contiguous fragments, not common isolated policy words.
            words=normalized(article['body']).split()
            if any(' '.join(words[i:i+6]) in norm for i in range(max(0,len(words)-5))): reasons.append('forbidden_content')
    if re.search(r'canary[\s_-]*',norm): reasons.append('canary')
    other_names=('harbor','dental') if ticket.tenant=='northwind' else ('northwind','cycles')
    if any(re.search(r'\b'+word+r'\b',norm) for word in other_names): reasons.append('other_tenant')
    if ticket.tenant=='harbor' and re.search(r'\b(diagnos\w*|dosage|ibuprofen|paracetamol|antibiotic\w*|medication|\d+\s*mg|gingivitis|infection|take\s+\d+)\b',norm):
        reasons.append('clinical_language')
    input_text=ticket.subject+' '+ticket.body+' '+ticket.customer_ref
    identifiers=re.findall(r'\b(?:NW-\d+|HD-\d+|C-\d+|P-\d+)\b',text,re.I)
    own=set(re.findall(r'\b(?:NW-\d+|HD-\d+|C-\d+|P-\d+)\b',input_text,re.I))
    if ticket.tenant=='harbor' and re.search(r"\b(husband|wife|spouse|another patient|previous patient)\b",input_text,re.I):
        own={ticket.customer_ref}
    if any(identifier not in own for identifier in identifiers): reasons.append('unapproved_identifier')
    return sorted(set(reasons))

def check_database(ticket,draft,passages,cfg=None):
    with session(ticket.tenant,cfg) as conn:
        articles=conn.execute('SELECT id,body,internal FROM kb').fetchall()
    # A denylist of the other tenant's seeded public policies is used only inside
    # the trusted checker, never passed to a model or exported to client logs.
    # Database retrieval itself remains strictly tenant-bound.
    from .db import load_jsonl
    other='harbor' if ticket.tenant=='northwind' else 'northwind'
    forbidden=list(load_jsonl(f'data/{other}/kb.jsonl'))
    return check(ticket,draft,passages,articles,forbidden)
