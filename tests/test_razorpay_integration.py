import hashlib, hmac, json, os
from fastapi.testclient import TestClient
os.environ['RAZORPAY_WEBHOOK_SECRET']='test-secret'
from recoveryos.integrations.webhook_app import app
client=TestClient(app)

def sign(raw):
    return hmac.new(b'test-secret',raw,hashlib.sha256).hexdigest()

def event_body(payment_id='pay_test_1', amount=250000, code='BAD_REQUEST_ERROR'):
    return {'event':'payment.failed','payload':{'payment.failed':{'entity':{
        'id':payment_id,'amount':amount,'status':'failed','error_code':code
    }}}}

def test_webhook_signature_and_failed_payment():
    raw=json.dumps(event_body(),separators=(',',':')).encode()
    r=client.post('/webhooks/razorpay',content=raw,headers={'X-Razorpay-Signature':sign(raw),'x-razorpay-event-id':'evt_1'})
    assert r.status_code==200
    assert r.json()['payment_id']=='pay_test_1'
    assert r.json()['decision_source'] in {'rule','ml'}

def test_duplicate_event_is_idempotent():
    raw=json.dumps(event_body('pay_test_2',100),separators=(',',':')).encode()
    h={'X-Razorpay-Signature':sign(raw),'x-razorpay-event-id':'evt_dup'}
    assert client.post('/webhooks/razorpay',content=raw,headers=h).status_code==200
    assert client.post('/webhooks/razorpay',content=raw,headers=h).json()['duplicate'] is True

def test_invalid_signature_rejected():
    raw=json.dumps(event_body(),separators=(',',':')).encode()
    r=client.post('/webhooks/razorpay',content=raw,headers={'X-Razorpay-Signature':'bad','x-razorpay-event-id':'evt_bad'})
    assert r.status_code==401
