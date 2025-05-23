
class UPIValidation:
    end_point = "/payout/v1/validation/upiDetails"
    req_type = "GET"

    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.vpa = kwargs["vpa"]