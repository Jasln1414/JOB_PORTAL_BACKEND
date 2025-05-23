import requests as rq
import json
from cashfree_sdk.payouts import payouts_config_var
from cashfree_sdk.exceptions.exceptions import *


def create_headers(token):
    bearer_token = "Bearer " + token
    headers = { 'Authorization' : bearer_token, 'Content-Type': 'application/json', 
        'cache-control': 'no-cache', 'User-Agent': 'Cashfree-SDK' }
    return headers

def trigger_request(params, *args, **kwargs):
    if params is None:
        return None
    request_type = getattr(params, "req_type")
    end_point = getattr(params, "end_point")
    if request_type == "GET":
        return make_get_request(end_point=end_point, params=params)
    elif request_type == "POST":
        return make_post_request(end_point=end_point, payload=params)


def make_get_request(end_point, params, *args, **kwargs):
    url = payouts_config_var.url + end_point
    token = payouts_config_var.token
    
    headers = create_headers(token)
    params_dict = {}
    if params:
        params_dict = params.__dict__
    res = rq.request("GET", url, headers=headers, params=params_dict)
    if res.status_code == 200:
        validate(data=res.text, headers=res.headers)
        return res
    raise ServiceDownError


def make_post_request(end_point, payload, *args, **kwargs):
    url = payouts_config_var.url + end_point
    token = payouts_config_var.token
    headers = create_headers(token)
    payload_json = ''
    if payload:
        payload_json = json.dumps(payload.__dict__)
    res = rq.request("POST", url, data=payload_json, headers=headers)
    if res.status_code == 200:
        validate(data=res.text, headers=res.headers)
        return res
    raise ServiceDownError


def validate(data, headers):
    if not headers:
        headers = {}
    if not data or data == "":
        raise UnknownErrorOccurredError("No subcode and msg response from the service")
    data_dict = json.loads(data)
    if "subCode" in data_dict and not (data_dict["subCode"] == "200"
       or data_dict["subCode"] == "201" or data_dict["subCode"] == "202"):
        msg = "Reason = "+ data_dict["message"] +  ":: response = " + json.dumps(data_dict) + \
        " request_id  = " + headers.get('X-Request-Id', '')
        sub_code = data_dict["subCode"]
        if sub_code == "400":
            raise BadRequestError(msg)
        elif sub_code == "401":
            raise AuthenticationFailureError(msg)
        elif sub_code == "403":
            raise ForbiddenError(msg)
        elif sub_code == "404":
            raise EntityDoesntExistError(msg)
        elif sub_code == "405":
            raise MethodNotAllowedError(msg)
        elif sub_code == "409":
            raise AlreadyExistError(msg)
        elif sub_code == "412":
            raise PreconditionFailedError(msg)
        elif sub_code == "413":
            raise RequestTooLargeError(msg)
        elif sub_code == "422":
            raise InputWrongFormatError(msg)
        elif sub_code == "424":
            raise RequestFailedError(msg)
        elif sub_code == "429":
            raise TooManyRequestError(msg)
        elif sub_code == "500":
            raise InternalServerError(msg)
        elif sub_code == "503":
            raise ServiceDownError(msg)
        elif sub_code == "520":
            raise UnknownErrorOccurredError(msg)
        else:
            raise UnknownErrorOccurredError(msg)
    elif ( ( "subCode" in data_dict and ( data_dict["subCode"] == "200"
       or data_dict["subCode"] == "201" )) or ("statusCode" in data_dict and data_dict["statusCode"] == "200") ): 
       return
    else:
        raise UnknownErrorOccurredError("No subcode and msg response from the service , response = " + data)
                



