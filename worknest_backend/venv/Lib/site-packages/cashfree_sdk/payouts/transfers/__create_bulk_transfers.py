

class CreateBulkTransfer:
    end_point = "/payout/v1/requestBatchTransfer"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.batchTransferId = kwargs["batchTransferId"]
        self.batchFormat = kwargs["batchFormat"]
        self.batch = kwargs["batch"]
        if kwargs.get("deleteBene"):
            self.deleteBene = kwargs["deleteBene"]

