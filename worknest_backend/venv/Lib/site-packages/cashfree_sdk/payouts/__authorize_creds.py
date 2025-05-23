import requests as rq
from . import payouts_config_var
import json
import time
import base64
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from cashfree_sdk.exceptions.exceptions import *

auth_endpoint = "/payout/v1/authorize"
verify_endpoint = "/payout/v1/verifyToken"
three_minutes_secs = 180

def authenticate():
    if not payouts_config_var or payouts_config_var.payout_creds.client_id == "" \
        or payouts_config_var.payout_creds.client_secret == "":
        raise ModuleNotInitiatedError 

    if payouts_config_var.token != "" and payouts_config_var.expiry != 0 and  (payouts_config_var.expiry - (time.time() + three_minutes_secs)) > 0:
        return

    if payouts_config_var.mode == "SIGNATURE" and payouts_config_var.payout_creds.public_key == b"":
        raise InvalidPublicKeyError()

    merchant_id = payouts_config_var.payout_creds.client_id
    merchant_secret = payouts_config_var.payout_creds.client_secret
    auth_url = payouts_config_var.url + auth_endpoint

    headers = { 
        'X-Client-Id': merchant_id,
        'X-Client-Secret': merchant_secret
    }

    if payouts_config_var.mode == "SIGNATURE":
        generate_signature()
        if payouts_config_var.signature == "":
            raise SignatureCreationFailedError()
        headers['X-Cf-Signature'] = payouts_config_var.signature

    res = rq.request("POST", auth_url, headers=headers)

    if res.status_code == 200:
        data = json.loads(res.text)
        if data and "subCode" in data and data["subCode"]:
            if data["subCode"] == "200":
                token = ""
                expiry = 0
                res_data = data.get("data")
                if res_data and "token" in res_data and "expiry" in res_data:
                    token = res_data["token"]
                    expiry = res_data["expiry"]
                else:
                    raise TokenGenFailedError
                if token and token != "":
                    if verify_token(token):
                        payouts_config_var.token = token
                        payouts_config_var.expiry = expiry
                        return
            else:
                raise IncorrectCredsError(data["message"])
        else:
            raise AuthenticationFailureError
    raise ServiceDownError

def generate_signature():
    if payouts_config_var.signature != "" and payouts_config_var.signature_expiry != 0 and (payouts_config_var.signature_expiry - time.time()) > 0:
        return
    cur_time = round(time.time())
    cur_time_str = str(cur_time) 
    encode_data = payouts_config_var.payout_creds.client_id + "." + cur_time_str
    encrypter = PKCS1_OAEP.new(RSA.importKey(payouts_config_var.payout_creds.public_key))
    signature = encrypter.encrypt(encode_data.encode())
    signature_str  = base64.b64encode(signature).decode("utf-8")
    payouts_config_var.signature = signature_str
    payouts_config_var.signature_expiry = cur_time + three_minutes_secs*2
    


def verify_token(token):
    verify_url = payouts_config_var.url + verify_endpoint
    headers = {
        'Authorization' : "Bearer "+ token
    }
    res = rq.request("POST", verify_url, headers=headers)

    if res.status_code == 200:
        data = json.loads(res.text)
        if data["status"] == "SUCCESS" and data["subCode"] == "200":
            return True
        return False
    
    raise ServiceDownError

def authorize(func):
    def authenticate_gen_token(*args, **kwargs):
        authenticate()
        return func(*args, **kwargs)
    return authenticate_gen_token








