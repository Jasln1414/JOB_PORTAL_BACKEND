
class GetValidationStatus:
    end_point = "/payout/v1/getValidationStatus/bank"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        if kwargs.get("userId"):
            self.userId = kwargs["userId"]
        if kwargs.get("bvRefId"):
            self.bvRefId = kwargs["bvRefId"]