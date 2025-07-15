# pragma version 0.4.3
"""
@notice Curve Arbitrum Bridge Wrapper
"""
from ethereum.ercs import IERC20
from snekmate.auth import ownable

initializes: ownable
exports: (
    ownable.owner,
    ownable.transfer_ownership,
    ownable.renounce_ownership,
)


interface GatewayRouter:
    def getGateway(_token: address) -> address: view
    def outboundTransfer(  # emits DepositInitiated event with Inbox sequence #
        _token: address,
        _to: address,
        _amount: uint256,
        _max_gas: uint256,
        _gas_price_bid: uint256,
        _data: Bytes[128],  # _max_submission_cost, _extra_data
    ): payable


struct SubmissionData:
    gas_limit: uint256
    gas_price: uint256
    max_submission_cost: uint256


event UpdateSubmissionData:
    _old_submission_data: SubmissionData
    _new_submission_data: SubmissionData


CRV20: constant(address) = 0xD533a949740bb3306d119CC777fa900bA034cd52
GATEWAY: constant(address) = 0xa3A7B6F88361F48403514059F1F16C8E78d60EeC
GATEWAY_ROUTER: constant(address) = 0x72Ce9c846789fdB6fC1f34aC4AD25Dd9ef7031ef


submission_data: public(SubmissionData)
is_approved: public(HashMap[address, bool])


@deploy
def __init__(_gas_limit: uint256, _gas_price: uint256, _max_submission_cost: uint256):
    ownable.__init__()
    ownable._transfer_ownership(tx.origin)
    
    self.submission_data = SubmissionData(
        gas_limit=_gas_limit,
        gas_price=_gas_price,
        max_submission_cost=_max_submission_cost
    )
    
    log UpdateSubmissionData(
        _old_submission_data=SubmissionData(gas_limit=0, gas_price=0, max_submission_cost=0),
        _new_submission_data=self.submission_data
    )

    assert extcall IERC20(CRV20).approve(GATEWAY, max_value(uint256))
    self.is_approved[CRV20] = True


@payable
@external
def bridge(_token: address, _to: address, _amount: uint256):
    """
    @notice Bridge an ERC20 token using the Arbitrum standard bridge
    @param _token The address of the token to bridge
    @param _to The address to deposit token to on L2
    @param _amount The amount of `_token` to deposit
    """
    assert extcall IERC20(_token).transferFrom(msg.sender, self, _amount)

    if _token != CRV20 and not self.is_approved[_token]:
        assert extcall IERC20(_token).approve(staticcall GatewayRouter(GATEWAY_ROUTER).getGateway(_token), max_value(uint256))
        self.is_approved[_token] = True

    data: SubmissionData = self.submission_data

    # NOTE: Excess ETH fee is refunded to this bridger's address on L2.
    # After bridging, the token should arrive on Arbitrum within 10 minutes. If it
    # does not, the L2 transaction may have failed due to an insufficient amount
    # within `max_submission_cost + (gas_limit * gas_price)`
    # In this case, the transaction can be manually broadcasted on Arbitrum by calling
    # `ArbRetryableTicket(0x000000000000000000000000000000000000006e).redeem(redemption-TxID)`
    # The calldata for this manual transaction is easily obtained by finding the reverted
    # transaction in the tx history for 0x000000000000000000000000000000000000006e on Arbiscan.
    # https://developer.offchainlabs.com/docs/l1_l2_messages#retryable-transaction-lifecycle
    extcall GatewayRouter(GATEWAY_ROUTER).outboundTransfer(
        _token,
        _to,
        _amount,
        data.gas_limit,
        data.gas_price,
        abi_encode(data.max_submission_cost, b""),
        value=data.gas_limit * data.gas_price + data.max_submission_cost
    )


@view
@external
def cost() -> uint256:
    """
    @notice Cost in ETH to bridge
    """
    data: SubmissionData = self.submission_data
    return data.gas_limit * data.gas_price + data.max_submission_cost


@pure
@external
def check(_account: address) -> bool:
    """
    @notice Verify if `_account` is allowed to bridge using `transmit_emissions`
    @param _account The account calling `transmit_emissions`
    """
    return True


@external
def set_submission_data(_gas_limit: uint256, _gas_price: uint256, _max_submission_cost: uint256):
    """
    @notice Update the arb retryable ticket submission data
    @param _gas_limit The gas limit for the retryable ticket tx
    @param _gas_price The gas price for the retryable ticket tx
    @param _max_submission_cost The max submission cost for the retryable ticket
    """
    ownable._check_owner()

    old_data: SubmissionData = self.submission_data
    new_data: SubmissionData = SubmissionData(
        gas_limit=_gas_limit,
        gas_price=_gas_price,
        max_submission_cost=_max_submission_cost
    )
    
    self.submission_data = new_data
    log UpdateSubmissionData(_old_submission_data=old_data, _new_submission_data=new_data)