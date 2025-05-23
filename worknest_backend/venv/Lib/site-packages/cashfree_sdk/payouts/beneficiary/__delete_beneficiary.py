


class DeleteBeneficiary:
    end_point = "/payout/v1/removeBeneficiary"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.beneId = kwargs["beneId"]