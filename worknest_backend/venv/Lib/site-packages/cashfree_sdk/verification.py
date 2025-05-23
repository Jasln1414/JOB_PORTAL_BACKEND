from urllib import parse
import json
import hmac
import hashlib
import base64
from cashfree_sdk.exceptions.exceptions import *
from cashfree_sdk.payouts import payouts_config_var


def verify_webhook(webhook_data, payload_type='FORM'):
    if not payload_type or payload_type not in ('FORM', 'JSON'):
        raise InvalidaWebHookPayloadTypeError()

    data = {}
    
    if payload_type == 'FORM':
        data = dict( (k, v if len(v)>1 else v[0] ) 
           for k, v in parse.parse_qs(webhook_data).items() )
        if len(data) == 0 or 'signature' not in data:
            return False
    else:
        data = json.loads(webhook_data)
        if len(data) == 0 or 'signature' not in data:
            return False
    
    return __verify_payload(data)

def __verify_payload(data):
    if payouts_config_var.payout_creds.client_secret == "":
        raise ModuleNotInitiatedError()

    key = payouts_config_var.payout_creds.client_secret
    signature = data['signature']
    sorted_data_dict = { key:data[key] for key in sorted(data) if key != 'signature'}
    val_str = "".join( str(val) for val in sorted_data_dict.values())
    
    hash_val = hmac.new(key.encode(), val_str.encode(), hashlib.sha256).digest()

    gen_signature = base64.b64encode(hash_val)
    if gen_signature == signature.encode():
        return True
    
    return False


