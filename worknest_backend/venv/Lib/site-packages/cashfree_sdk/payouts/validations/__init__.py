from .. import __request as request
from ..__authorize_creds import authorize
from .__bank_det_valid import BankDetailsValidation
from .__upi_validation import UPIValidation
from .__bulk_bank_validation import BulkBankValidation
from .__get_bulk_bank_valid_status import GetBulkBankValidationStatus
from .__bank_det_valid_v1_2 import BankDetailsValidationV1V2
from .__async_bank_det_valid import AsyncBankDetailsValidation
from .__validation_status import GetValidationStatus


class Validations:
    
    @staticmethod
    @authorize
    def bank_details_validation(bankAccount, ifsc, name, phone):
        r""" Validate bank details by penny drop.
        :param bankAccount: bankAccount.
        :param ifsc: ifsc.
        :param name: name.
        :param phone: phone.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        bank_det_valid_req = BankDetailsValidation(bankAccount=bankAccount, ifsc=ifsc, 
            name=name, phone=phone)
        return request.trigger_request(bank_det_valid_req)

    @staticmethod
    @authorize
    def upi_validation(name, vpa):
        r""" Validate upi details by penny drop.
        :param name: name.
        :param vpa: vpa.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        upi_valid_req = UPIValidation(name=name, vpa=vpa)
        return request.trigger_request(upi_valid_req)

    @staticmethod
    @authorize
    def bulk_bank_validation(bulkValidationId, entries):
        r""" Validate bulk bank details by penny drop.
        :param bulkValidationId: bulkValidationId.
        :param entries: entries.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        bulk_bank_valid_req = BulkBankValidation(bulkValidationId=bulkValidationId, entries=entries)
        return request.trigger_request(bulk_bank_valid_req)

    @staticmethod
    @authorize
    def get_bulk_bank_validation_status(bulkValidationId, **kwargs):
        r""" Get bulk bank validation status.
        :param bulkValidationId: bulkValidationId.
        :param bankAccount: (optional) bankAccount.
        :param ifsc: (optional) ifsc.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        get_bulk_valid_status_req = GetBulkBankValidationStatus(bulkValidationId=bulkValidationId, **kwargs)
        return request.trigger_request(get_bulk_valid_status_req)

    @staticmethod
    @authorize
    def bank_details_validation_v1_2(bankAccount, ifsc, **kwargs):
        r""" Validate bank details by penny drop V1.2 Endpoint.
        :param bankAccount: bankAccount.
        :param ifsc: ifsc.
        :param name: (optional) name.
        :param phone: (optional) phone.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        bank_det_valid_req = BankDetailsValidationV1V2(bankAccount=bankAccount, ifsc=ifsc, 
            **kwargs)
        return request.trigger_request(bank_det_valid_req)

    @staticmethod
    @authorize
    def async_bank_details_validation(bankAccount, ifsc, name, phone, **kwargs):
        r""" Async Validate bank details by penny drop, requirs check status for requested validation
        :param bankAccount: bankAccount.
        :param ifsc: ifsc.
        :param name: name.
        :param phone: phone.
        :param userId: (optional) User generated id for check status later.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        async_valid_req = AsyncBankDetailsValidation(bankAccount=bankAccount, ifsc=ifsc, 
            name=name, phone=phone, **kwargs)
        return request.trigger_request(async_valid_req)

    @staticmethod
    @authorize
    def get_bank_validation_status(**kwargs):
        r""" Get bank validation status, either bvRefId or userId is required
        :param bvRefId: (optional)bvRefId.
        :param userId: (optional) userId.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        validation_status_req = GetValidationStatus(**kwargs)
        return request.trigger_request(validation_status_req)