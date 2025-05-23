from .. import __request as request
from ..__authorize_creds import authorize
from .__create_cashgram import CreateCashgram
from .__get_cashgram_status import GetCashgramStatus
from .__deactivate_cashgram import DeactivateCashgram

class Cashgram:

    @staticmethod
    @authorize
    def create_cashgram(cashgramId, amount, name, phone, linkExpiry, **kwargs):
        r"""Create Cashgram payouts Link.
        :param cashgramId: cashgramId.
        :param amount: amount.
        :param name: name.
        :param phone: phone.
        :param linkExpiry: linkExpiry.
        :param email: (optional) email.
        :param remarks: (optional) remarks.
        :param notifyCustomer: (optional) notifyCustomer.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        create_cashgram_req = CreateCashgram(cashgramId=cashgramId, amount=amount, 
            name=name, phone=phone, linkExpiry=linkExpiry, **kwargs)
        return request.trigger_request(create_cashgram_req)

    @staticmethod
    @authorize
    def get_cashgram_status(cashgramId):
        r"""Get cashgram link status.
        :param cashgramId: CashgramId.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        get_cashgram_status = GetCashgramStatus(cashgramId=cashgramId)
        return request.trigger_request(get_cashgram_status)

    @staticmethod
    @authorize
    def deactivate_cashgram(cashgramId):
        r"""Deactivate Cashgram Links To avoid them to be refunded. 
        :param cashgramId: CashgramId.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        deactivate_cashgram_req = DeactivateCashgram(cashgramId=cashgramId)
        return request.trigger_request(deactivate_cashgram_req)
