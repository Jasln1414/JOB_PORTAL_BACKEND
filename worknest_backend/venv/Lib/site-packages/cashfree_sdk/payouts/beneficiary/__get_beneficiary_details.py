
class GetBeneFiciaryDetails:
    end_point = "/payout/v1/getBeneficiary"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        if kwargs.get("beneId"):
            self.beneId = kwargs.get["beneId"]