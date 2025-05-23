from .__bank_det_valid import BankDetailsValidation

class BankDetailsValidationV1V2(BankDetailsValidation):
    end_point = "/payout/v1.2/validation/bankDetails"

    def __init__(self, *args, **kwargs):
        if kwargs.get("name"):
            self.name = kwargs["name"]
        if kwargs.get("phone"):
            self.name = kwargs["phone"]
        self.bankAccount = kwargs["bankAccount"]
        self.ifsc = kwargs["ifsc"]