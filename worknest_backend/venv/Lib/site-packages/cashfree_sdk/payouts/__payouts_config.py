from .__payouts_creds import PayoutCreds

class PayoutsConfig:
    
    def __init__(self):
        self.payout_creds = PayoutCreds()
        self.env = "TEST"
        self.url = "https://payout-gamma.cashfree.com"
        self.token = ""
        self.expiry = 0
        self.signature = ""
        self.signature_expiry = 0
        self.mode = "IP"

    def init_creds(self, client_id, client_secret, env):
        self.payout_creds.set_creds(client_secret=client_secret, client_id=client_id)
        self.env = env or "TEST"
        if env == "PROD":
            self.url = "https://payout-api.cashfree.com"

    def init_signature_creds(self, client_id, client_secret, env, **kwargs):
        self.init_creds(client_id, client_secret, env)
        self.mode = "SIGNATURE"
        if "public_key" in kwargs:
            self.payout_creds.set_public_key(public_key=kwargs["public_key"])
        else:
            self.payout_creds.set_public_key(public_key_file=kwargs["public_key_path"])
