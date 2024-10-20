"""
binary utility functions
- query bank balance
- query tx
- node status
- tx bank send
"""

import json
import subprocess
import logging


def getBalance(binary: str, address: str, datadir: str, node: str):
    """
    geth --datadir <datadir> --exec "eth.getBalance('<address>')" attach <node>
    """
    balance = subprocess.run([binary, "--datadir", datadir, "--exec",
                              f"eth.getBalance('{address}')",
                              "attach", node],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
    try:
        balance.check_returncode()
        return(balance.stdout.replace('\n', '').strip())
    except subprocess.CalledProcessError as cpe:
        output = str(balance.stderr).split('\n', maxsplit=1)
        logging.error("Called Process Error: %s, stderr: %s", cpe, output)
        raise cpe
    except IndexError as index_error:
        logging.error('Parsing error on balance request: %s', index_error)
        raise index_error
    return None

def unlock(binary: str, address: str, datadir: str, node: str):
    """
    geth --datadir <datadir> --exec "personal.unlockAccount('<address>', '<password>', <time>)" attach <node>
    """
    balance = subprocess.run([binary, "--datadir", datadir, "--exec",
                              f"personal.unlockAccount('{address}','1',300)",
                              "attach", node],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
    try:
        balance.check_returncode()
        if (balance.stdout.replace('\n', '').strip() == "true"):
            return True
        else: return False
    except subprocess.CalledProcessError as cpe:
        output = str(balance.stderr).split('\n', maxsplit=1)
        logging.error("Called Process Error: %s, stderr: %s", cpe, output)
        raise cpe
    except IndexError as index_error:
        logging.error('Parsing error on balance request: %s', index_error)
        raise index_error
    return None

def sendTX(binary: str, sender: str, recipient: str, amount: str, datadir: str, node: str):
    """
    The request dictionary must include these keys:
    - "sender"
    - "recipient"
    - "amount"
    geth --datadir <datadir> --exec "eth.sendTransaction({from:'<sender>',to:'<recipient>',value:'<amount>'})" attach <node>

    """
    tx_gaia = subprocess.run([binary, '--datadir', datadir, '--exec',
                              f"eth.sendTransaction({{from:'{sender}',to:'{recipient}',value:'{amount}'}})",
                              "attach", node],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return tx_gaia.stdout.replace('\n', '').strip()
    except subprocess.CalledProcessError as cpe:
        output = str(tx_gaia.stderr).split('\n', maxsplit=1)
        logging.error("%s[%s]", cpe, output)
        raise cpe
    except (TypeError, KeyError) as err:
        output = tx_gaia.stderr
        logging.critical(
            'Could not read %s in tx response: %s', err, output)
        raise err
    return None