
from .__create_beneficiary import CreateBeneficiary
from .__get_beneficiary_details import GetBeneFiciaryDetails
from .__get_beneficiary_id import GetBeneficiaryId
from .__delete_beneficiary import DeleteBeneficiary
from .. import __request as request
from ..__authorize_creds import authorize

class Beneficiary():
    
    @staticmethod
    @authorize
    def add(beneId, name, email, phone, address1, **kwargs):
        r"""Create Beneficiary.
        :param beneId: BeneId.
        :param name: Name.
        :param email: Email.
        :param phone: Phone.
        :param address1: Address1.
        :param group: (optional) Group.
        :param bankAccount: (optional) bankAccount.
        :param ifsc: (optional) ifsc.
        :param vpa: (optional) vpa.
        :param cardNo: (optional) cardNo.
        :param address2: (optional) address2.
        :param city: (optional) city.
        :param state: (optional) state.
        :param pincode: (optional) pincode.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        create_bene_req = CreateBeneficiary(beneId=beneId, name=name, email=email, phone=phone, address1=address1
            , **kwargs)
        return request.trigger_request(create_bene_req)

    @staticmethod
    @authorize
    def get_bene_details(beneId):
        r"""Get Beneficiary Details.
        :param beneId: BeneId.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        get_bene_req = GetBeneFiciaryDetails()
        get_bene_req.end_point += "/" + beneId
        return request.trigger_request(get_bene_req)

    @staticmethod
    @authorize
    def get_bene_id(bankAccount, ifsc):
        r"""Get bene Id for given bankaccount and IFSC.
        :param bankAccount: BankAccount.
        :param ifsc: ifsc.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        get_bene_id_req = GetBeneficiaryId(bankAccount=bankAccount, ifsc=ifsc)
        return request.trigger_request(get_bene_id_req) 
    
    @staticmethod
    @authorize
    def remove_bene(beneId):
        r"""Delete Bene.
        :param beneId: BeneId.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        del_bene_req = DeleteBeneficiary(beneId=beneId)
        return request.trigger_request(del_bene_req)