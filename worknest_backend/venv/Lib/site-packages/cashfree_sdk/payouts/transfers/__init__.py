from .. import __request as request
from ..__authorize_creds import authorize
from .__get_balance import GetBalance
from .__request_transfer import RequestTransfer
from .__get_transfer_status import GetTransferStatus
from .__list_transfers import ListTransfers
from .__create_bulk_transfers import CreateBulkTransfer
from .__get_bulk_transfer_status import GetBulkTransferStatus
from .__self_withdrawal import SelfWithdrawal
from .__async_request_transfer import AsyncRequestTransfer


class Transfers:
    @staticmethod
    @authorize
    def get_balance():
        """Fetch Balance present in payouts account. 
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        get_bal_req = GetBalance()
        return request.trigger_request(get_bal_req)

    @staticmethod
    @authorize
    def request_transfer(beneId, transferId, amount, **kwargs):
        """Request Transfer.
        :param beneId: BeneId.
        :param transferId: transferId.
        :param amount: amount.
        :param transferMode: (optional) transferMode.
        :param remarks: (optional) remarks.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        req_transfer_req = RequestTransfer(beneId=beneId, transferId=transferId, amount=amount, **kwargs)
        return request.trigger_request(req_transfer_req)

    @staticmethod
    @authorize
    def get_transfer_status(**kwargs):
        """Get Transfer Status.
        :param referenceId: (1)referenceId.
        :param transferId: (2)transferId.
        Either one param is mandatory to fetch status.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        get_transfer_status_req = GetTransferStatus(**kwargs)
        return request.trigger_request(get_transfer_status_req)

    @staticmethod
    @authorize
    def list_transfers(**kwargs):
        """List the transfers with optional params for more specific data.
        :param maxReturn: (optional) maxReturn.
        :param lastReturnId: (optional) lastReturnId.
        :param date: (optional) date.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        list_transfer_req = ListTransfers(**kwargs)
        return request.trigger_request(list_transfer_req)
    

    @staticmethod
    @authorize
    def create_batch_transfer(batchTransferId, batchFormat, batch, **kwargs):
        """Create batch transfers for list of bankaccount or beneId.
        :param batchTransferId: batchTransferId.
        :param batchFormat: batchFormat.
        :param batch: batch.
        :param deleteBene: (optional) deleteBene.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        create_batch_transfer_req = CreateBulkTransfer(batchTransferId=batchTransferId, batchFormat=batchFormat,
            batch=batch, **kwargs)
        return request.trigger_request(create_batch_transfer_req)

    @staticmethod
    @authorize
    def get_batch_transfer_status(batchTransferId):
        """Fetch status of batch transfer.
        :param batchTransferId: batchTransferId.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        get_bulk_transfer_status_req = GetBulkTransferStatus(batchTransferId=batchTransferId)
        return request.trigger_request(get_bulk_transfer_status_req)

    @staticmethod
    @authorize
    def self_withdrawal(withdrawalId, amount, **kwargs):
        """ Create a self withdrawal from own payout balance.
        :param withdrawalId: withdrawalId.
        :param amount: amount.
        :param remarks: (optional) remarks.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        self_withd_req = SelfWithdrawal(withdrawalId=withdrawalId, amount=amount, **kwargs)
        return request.trigger_request(self_withd_req)

    @staticmethod
    @authorize
    def async_request_transfer(beneId, transferId, amount, **kwargs):
        """Async Request Transfer.
        :param beneId: BeneId.
        :param transferId: transferId.
        :param amount: amount.
        :param transferMode: (optional) transferMode.
        :param remarks: (optional) remarks.
        :return: :class:`Response <Response>` object.
        :rtype: requests.Response.
        """
        req_transfer_req = AsyncRequestTransfer(beneId=beneId, transferId=transferId, amount=amount, **kwargs)
        return request.trigger_request(req_transfer_req)


