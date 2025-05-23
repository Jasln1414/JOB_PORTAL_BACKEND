
class CreateCashgram:
    end_point = "/payout/v1/createCashgram"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.cashgramId = kwargs["cashgramId"]
        self.amount = kwargs["amount"]
        self.name = kwargs["name"]
        self.phone = kwargs["phone"]
        self.linkExpiry = kwargs["linkExpiry"]
        if kwargs.get("email"):
            self.email = kwargs["email"]
        if kwargs.get("remarks"):
            self.remarks = kwargs["remarks"]
        if kwargs.get("notifyCustomer"):
            self.notifyCustomer = kwargs["notifyCustomer"]
        