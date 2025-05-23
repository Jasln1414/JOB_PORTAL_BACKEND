

class BankDetailsValidation:
    end_point = "/payout/v1/validation/bankDetails"
    req_type = "GET"

    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.phone = kwargs["phone"]
        self.bankAccount = kwargs["bankAccount"]
        self.ifsc = kwargs["ifsc"]