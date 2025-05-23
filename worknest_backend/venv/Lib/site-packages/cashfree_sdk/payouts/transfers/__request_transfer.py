
class RequestTransfer:
    end_point = "/payout/v1/requestTransfer"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.beneId = kwargs["beneId"]
        self.amount = kwargs["amount"]
        self.transferId = kwargs["transferId"]
        if kwargs.get("transferMode"):
            self.transferMode = kwargs["transferMode"]
        if kwargs.get("remarks"):
            self.remarks = kwargs["remarks"]