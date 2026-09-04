def naive(case):
    return "retry_now"
def strong_rules(case):
    c,r,mf,s=case.failure_code,case.retry_count,case.merchant_recent_failure_rate,case.customer_previous_success_rate
    if c=="EXPIRED_CODE": return "request_alternate_method"
    if c=="INSUFFICIENT_FUNDS_CODE": return "retry_later"
    if r>=3: return "request_alternate_method"
    if mf>=.20 and c in {"TIMEOUT","NETWORK_ERROR","DECLINED"}: return "retry_later"
    if c=="DECLINED" and s<.65: return "request_alternate_method"
    return "retry_now"
