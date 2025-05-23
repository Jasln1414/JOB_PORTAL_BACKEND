from .__bank_det_valid import BankDetailsValidation


class AsyncBankDetailsValidation(BankDetailsValidation):
    end_point = "/payout/v1/asyncValidation/bankDetails"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if kwargs.get("userId"):
            self.userId = kwargs["userId"]
        