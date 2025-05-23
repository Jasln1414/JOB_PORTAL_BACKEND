

class GetTransferStatus:
    end_point = "/payout/v1/getTransferStatus"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        if kwargs.get("referenceId"):
            self.referenceId = kwargs["referenceId"] 
        if kwargs.get("transferId"):
            self.transferId = kwargs["transferId"]
        
