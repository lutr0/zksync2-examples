import json
import os
from pathlib import Path

from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_typing import HexStr
import requests


from zksync2.core.types import EthBlockParams, PaymasterParams
from zksync2.manage_contracts.contract_encoder_base import ContractEncoder, JsonConfiguration
from zksync2.manage_contracts.paymaster_utils import PaymasterFlowEncoder
from zksync2.module.module_builder import ZkSyncBuilder
from zksync2.signer.eth_signer import PrivateKeyEthSigner
from zksync2.transaction.transaction_builders import TxFunctionCall


def get_abi_from_standard_json(standard_json: Path):
    with standard_json.open(mode="r") as json_f:
        return json.load(json_f)["abi"]


"""
This example demonstrates how to use a paymaster to facilitate fee payment with an ERC20 token.
The user initiates a mint transaction that is configured to be paid with an ERC20 token through the paymaster.
During transaction execution, the paymaster receives the ERC20 token from the user and covers the transaction fee using ETH.
"""
if __name__ == "__main__":
    # Set a provider
    PROVIDER = "https://sepolia.era.zksync.dev"

    # Get the private key from OS environment variables
    PRIVATE_KEY = HexStr("c273a8616a4c58de9e58750fd2672d07b10497d64cd91b5942cce0909aaa391a")

    # Connect to zkSync network
    zk_web3 = ZkSyncBuilder.build(PROVIDER)

    # Get account object by providing from private key
    account: LocalAccount = Account.from_key(PRIVATE_KEY)

    # Crown token than can be minted for free
    token_address = zk_web3.to_checksum_address("0x927488F48ffbc32112F1fF721759649A89721F8F")
    # Paymaster for Crown token

    # Provide a compiled JSON source contract
    contract_path = Path("../solidity/custom_paymaster/token/build/Token.json")
    token_json = ContractEncoder.from_json(zk_web3, contract_path, JsonConfiguration.STANDARD)

    token_contract = zk_web3.zksync.contract(token_address, abi=token_json.abi)

    # MINT TOKEN TO USER ACCOUNT (so user can pay fee with token)
    balance = token_contract.functions.balanceOf(account.address).call()
    print(f"Crown token balance before mint: {balance}")

    mint_tx = token_contract.functions.mint(account.address, 50).build_transaction({
        "nonce": zk_web3.zksync.get_transaction_count(account.address, EthBlockParams.LATEST.value),
        "from": account.address,
        "maxPriorityFeePerGas": 1_000_000,
        "maxFeePerGas": zk_web3.zksync.gas_price,
    })

    signed = account.sign_transaction(mint_tx)

    # Send mint transaction to zkSync network
    tx_hash = zk_web3.zksync.send_raw_transaction(signed.rawTransaction)

    tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(
        tx_hash, timeout=240, poll_latency=0.5
    )
    print(f"Tx status: {tx_receipt['status']}")

    balance = token_contract.functions.balanceOf(account.address).call()
    print(f"Crown token balance after mint: {balance}")

    
    # USE PAYMASTER TO PAY MINT TRANSACTION WITH CROWN TOKEN

    # Use the paymaster to pay mint transaction with token
    url = 'https://api.zyfi.org/api/erc20_paymaster/v1'

    calladata = token_contract.encodeABI(fn_name="mint", args=[account.address, 7])

payload = {
    "feeTokenAddress": token_contract.address,
    "isTestnet": True,
    "txData": {
        "from": account.address,
        "to": "token_address",
        "data": calladata
    }
}
# Sending a POST request to the API endpoint
response = requests.post(url, json=payload)
response_data = response.json()

# Extracting data from the response
tx_data = response_data['txData']

# Setting up parameters based on the response
chain_id = tx_data['chainId']
from_address = tx_data['from']
to_address = tx_data['to']
data = tx_data['data']
paymaster_params = tx_data['customData']['paymasterParams']
gas_limit = tx_data['gasLimit']
max_fee_per_gas = tx_data['maxFeePerGas']


  tx_func_call = TxFunctionCall(
    chain_id=chain_id,
    nonce=zk_web3.zksync.get_transaction_count(account.address, EthBlockParams.LATEST.value),
    from_=from_address,
    to=to_address,
    data=data,
    gas_limit=gas_limit,  # Unknown at this state, estimation is done in next step
    gas_price=max_fee_per_gas,
    max_priority_fee_per_gas=0,
    paymaster_params=paymaster_params
)

    # Sign message & encode it
    signed_message = signer.sign_typed_data(tx_func_call.to_eip712_struct())

    # Encode signed message
    msg = tx_712.encode(signed_message)

    # Transfer ETH
    tx_hash = zk_web3.zksync.send_raw_transaction(msg)
    print(f"Transaction hash is : {tx_hash.hex()}")

    # Wait for transaction to be included in a block
    tx_receipt = zk_web3.zksync.wait_for_transaction_receipt(
        tx_hash, timeout=240, poll_latency=0.5
    )
    print(f"Tx status: {tx_receipt['status']}")

    print(f"Paymaster balance after mint: "
          f"{zk_web3.zksync.get_balance(account.address, EthBlockParams.LATEST.value)}")
    print(f"User's Crown token balance after mint: {token_contract.functions.balanceOf(account.address).call()}")
    print(f"Paymaster balance after mint: "
          f"{zk_web3.zksync.get_balance(paymaster_address, EthBlockParams.LATEST.value)}")
    print(f"Paymaster Crown token balance after mint: {token_contract.functions.balanceOf(paymaster_address).call()}")
