import os, json, hmac, hashlib
os.environ['RAZORPAY_WEBHOOK_SECRET']='test-secret'
from fastapi.testclient import TestClient
from recoveryos.integrations.webhook_app import app
client=TestClient(app)
def sign(raw): return hmac.new(b'test-secret', raw, hashlib.sha256).hexdigest()

def test_health():
    r=client.get('/health'); assert r.status_code==200; assert r.json()['decision_engine']=='rules_then_ml_then_agent_on_ambiguity'

def test_payment_failed_flows_into_rules_or_ml():
    body={'event':'payment.failed','payload':{'payment.failed':{'entity':{
        'id':'pay_livepath_1','order_id':'order_1','amount':250000,'status':'failed','error_code':'EXPIRED_CODE',
        'notes':{'historical_retry_count':'1','customer_success_rate':'0.8','merchant_failure_rate':'0.1'}
    }}}}
    raw=json.dumps(body,separators=(',',':')).encode(); h={'X-Razorpay-Signature':sign(raw),'x-razorpay-event-id':'evt_livepath_1'}
    r=client.post('/webhooks/razorpay',content=raw,headers=h); assert r.status_code==200
    data=r.json(); assert data['decision_source']=='rule'; assert data['selected_action']=='request_alternate_method'

def test_duplicate_is_ignored():
    body={'event':'payment.failed','payload':{'payment.failed':{'entity':{'id':'pay_dup','amount':1000,'error_code':'TIMEOUT'}}}}
    raw=json.dumps(body,separators=(',',':')).encode(); h={'X-Razorpay-Signature':sign(raw),'x-razorpay-event-id':'evt_dup_live'}
    assert client.post('/webhooks/razorpay',content=raw,headers=h).status_code==200
    assert client.post('/webhooks/razorpay',content=raw,headers=h).json()['duplicate'] is True

def test_bad_signature_rejected():
    raw=b'{"event":"payment.failed"}'
    r=client.post('/webhooks/razorpay',content=raw,headers={'X-Razorpay-Signature':'bad','x-razorpay-event-id':'evt_bad'})
    assert r.status_code==401
