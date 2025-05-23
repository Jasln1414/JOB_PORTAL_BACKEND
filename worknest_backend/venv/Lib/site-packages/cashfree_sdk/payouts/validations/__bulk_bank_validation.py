
class BulkBankValidation:
    end_point = "/payout/v1/bulkValidation/bankDetails"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.bulkValidationId = kwargs["bulkValidationId"]
        self.entries = kwargs["entries"]