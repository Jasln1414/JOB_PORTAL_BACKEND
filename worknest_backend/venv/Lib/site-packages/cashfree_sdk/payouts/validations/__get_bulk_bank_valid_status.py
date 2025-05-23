
class GetBulkBankValidationStatus:
    end_point = "/payout/v1/getBulkValidationStatus"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        self.bulkValidationId = kwargs["bulkValidationId"]
        if kwargs.get("bankAccount"):
            self.bankAccount = kwargs["bankAccount"]
        if kwargs.get("ifsc"):
            self.ifsc = kwargs["ifsc"]