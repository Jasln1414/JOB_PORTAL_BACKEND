from .__payouts_creds import PayoutCreds
from .__payouts_config import PayoutsConfig

payouts_config_var = PayoutsConfig()

class Payouts():

    @staticmethod
    def init(client_id, client_secret, env, *args, **kwargs):
        global payouts_config_var
        if not ("public_key_path" in kwargs or "public_key" in kwargs):
            payouts_config_var.init_creds(client_id=client_id, client_secret=client_secret, env=env)
        else:
            payouts_config_var.init_signature_creds(client_id=client_id, client_secret=client_secret, env=env, 
                **kwargs)


                
           
