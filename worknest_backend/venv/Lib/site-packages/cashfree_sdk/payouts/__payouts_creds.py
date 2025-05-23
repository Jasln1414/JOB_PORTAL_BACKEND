from cashfree_sdk.exceptions.exceptions import *
import pem

class PayoutCreds:

    def __init__(self):
        self.client_id = ""
        self.client_secret = ""
        self.public_key = b""
        self.public_key_file = ""

    def set_creds(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
    
    def set_public_key(self, **kwargs):
        if not ( "public_key" in kwargs or "public_key_file" in kwargs or 
            kwargs["public_key"] == "" or kwargs["public_key"] == b""):
            raise ConfigMissingForSignatureAuth()
        if "public_key_file" in kwargs:
            certs = pem.parse_file(kwargs["public_key_file"])
            self.public_key = certs[0].as_bytes()
        else:
            if type(kwargs["public_key"]) == str :
                self.public_key = kwargs["public_key"].encode()
            elif type(kwargs["public_key"]) == bytes:
                pass
            else:
                raise InvalidPublicKeyError()






        