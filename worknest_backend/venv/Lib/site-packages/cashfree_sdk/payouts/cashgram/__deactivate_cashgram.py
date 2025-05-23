

class DeactivateCashgram:
    end_point = "/payout/v1/deactivateCashgram"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.cashgramId = kwargs["cashgramId"]