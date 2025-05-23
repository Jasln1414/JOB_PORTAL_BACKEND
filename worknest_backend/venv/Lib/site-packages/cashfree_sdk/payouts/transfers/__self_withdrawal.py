

class SelfWithdrawal:
    end_point = "/payout/v1/selfWithdrawal"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.withdrawalId = kwargs["withdrawalId"]
        self.amount = kwargs["amount"]
        if kwargs.get("remarks"):
            self.remarks = kwargs["remarks"]
