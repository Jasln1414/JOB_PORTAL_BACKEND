class CreateBeneficiary:
    end_point = "/payout/v1/addBeneficiary"
    req_type = "POST"

    def __init__(self, *args, **kwargs):
        self.beneId = kwargs["beneId"]
        self.name = kwargs["name"]
        self.email = kwargs["email"]
        self.phone = kwargs["phone"]
        self.address1 = kwargs["address1"]
        if kwargs.get("bankAccount"):
            self.bankAccount = kwargs.get("bankAccount")
        if kwargs.get("ifsc"):
            self.ifsc = kwargs.get("ifsc")
        if kwargs.get("vpa"):
            self.vpa = kwargs.get("vpa") or ""
        if kwargs.get("vpa"):
            self.cardNo = kwargs.get("cardNo") or ""
        if kwargs.get("address2"):
            self.address2 = kwargs.get("address2") or ""
        if kwargs.get("city"):
            self.city = kwargs.get("city") or ""
        if kwargs.get("state"):
            self.state = kwargs.get("state") or ""
        if kwargs.get("pincode"):
            self.pincode = kwargs.get("pincode") or ""
        
        
        
        
