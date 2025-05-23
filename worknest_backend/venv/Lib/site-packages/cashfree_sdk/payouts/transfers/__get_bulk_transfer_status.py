

class GetBulkTransferStatus:
    end_point = "/payout/v1/getBatchTransferStatus"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        self.batchTransferId = kwargs["batchTransferId"]