

class GetCashgramStatus:
    end_point = "/payout/v1/getCashgramStatus"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        self.cashgramId = kwargs["cashgramId"]