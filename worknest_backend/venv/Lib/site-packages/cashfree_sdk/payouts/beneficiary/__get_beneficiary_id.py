

class GetBeneficiaryId:
    end_point = "/payout/v1/getBeneId"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        self.bankAccount = kwargs["bankAccount"]
        self.ifsc = kwargs["ifsc"]