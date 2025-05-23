


class ListTransfers:
    end_point = "/payout/v1/getTransfers"
    req_type = "GET"

    def __init__(self, *args, **kwargs):
        if kwargs.get("maxReturn"):
            self.maxReturn = kwargs["maxReturn"]
        if kwargs.get("lastReturnId"):
            self.lastReturnId = kwargs["lastReturnId"]
        if kwargs.get("date"):
            self.date = kwargs["date"]