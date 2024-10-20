import time
import datetime
import logging
import sys
from tabulate import tabulate
import aiofiles as aiof
import toml
import discord
import calls
from convert import export_pub_key
import traceback

activeRequests = {}
reqTimeout = 0

disc_log = logging.getLogger('discord')
disc_log.setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def getConfig():
    global activeRequests, reqTimeout
    config = toml.load('config.toml')

    try:
        reqTimeout = int(config['discord']['request_timeout'])
        LISTENING_CHANNELS = list(config['discord']['channels_to_listen'].split(','))
        config['discord']['channels_to_listen'] = LISTENING_CHANNELS
        networks = config['networks']
        for net in networks:
            print(f"Found configurations for chain {net}!")
            networks[net]["active_day"] = datetime.datetime.today().date()
            networks[net]["day_tally"] = 0
        activeRequests = {net: {} for net in networks}
    except KeyError as key:
        logging.critical('Key could not be found: %s', key)
        sys.exit()
    return config

async def export(transaction: str):
    """
    Transaction strings are already comma-separated
    """
    async with aiof.open('transactions.csv', 'a') as csv_file:
        await csv_file.write(f'{transaction}\n')
        await csv_file.flush()

async def getFaucetBalance(network: dict):
    """
    Returns the upicax balance
    """
    balance = calls.getBalance(
        binary = network['binary'],
        address = network['faucet_address'],
        datadir = network['data_dir'],
        node = network['node_url']
    )
    return balance + network['denomination']

async def getBalance(message, address, network: dict):
    """
    Provide the balance for a given address and network
    """
    reply = ''
    try:
        balance = calls.getBalance(
            binary = network['binary'],
            address = address,
            datadir = network['data_dir'],
            node = network["node_url"]
        )
        reply = f'Balance for address `{address}` in `{network["chain_id"]}`:\n```'
        reply = reply + balance
        reply = reply + '\n```\n'
    except Exception:
        reply = '❗ could not handle your request'
        traceback.print_exc()
    await message.reply(reply)

def check_time_limits(requester: str, address: str, network: dict):
    """
    Returns True, None if the given requester and address are not time-blocked for the given testnet
    Returns False, reply if either of them is still on time-out; msg is the reply to the requester
    """
    message_timestamp = time.time()
    # Check user allowance
    if requester in activeRequests[network['chain_id']]:
        check_time = activeRequests[network['chain_id']
                                     ][requester]['next_request']
        if check_time > message_timestamp:
            seconds_left = check_time - message_timestamp
            minutes_left = seconds_left / 60
            if minutes_left > 120:
                wait_time = str(int(minutes_left/60)) + ' hours'
            else:
                wait_time = str(int(minutes_left)) + ' minutes'
            timeout_in_hours = int(reqTimeout / 60 / 60)
            timeout_in_hours = int(reqTimeout / 60 / 60)
            reply = '🚫 You can request coins no more than once every' \
                f' {timeout_in_hours} hours for the same testnet, ' \
                f'please try again in ' \
                f'{wait_time}'
            return False, reply
        del activeRequests[network['chain_id']][requester]

    # Check address allowance
    if address in activeRequests[network['chain_id']]:
        check_time = activeRequests[network['chain_id']][address]['next_request']
        if check_time > message_timestamp:
            seconds_left = check_time - message_timestamp
            minutes_left = seconds_left / 60
            if minutes_left > 120:
                wait_time = str(int(minutes_left/60)) + ' hours'
            else:
                wait_time = str(int(minutes_left)) + ' minutes'
            timeout_in_hours = int(reqTimeout / 60 / 60)
            reply = '🚫 You can request coins no more than once every' \
                f' {timeout_in_hours} hours, for the same testnet, ' \
                f'please try again in ' \
                f'{wait_time}'
            return False, reply
        del activeRequests[network['chain_id']][address]

    if requester not in activeRequests[network['chain_id']] and \
       address not in activeRequests[network['chain_id']]:
        activeRequests[network['chain_id']][requester] = {
            'next_request': message_timestamp + reqTimeout}
        activeRequests[network['chain_id']][address] = {
            'next_request': message_timestamp + reqTimeout}

    return True, None

def check_daily_cap(network: dict):
    """
    Returns True if the faucet has not reached the daily cap
    Returns False otherwise
    """
    delta = int(network["amount_to_send"])
    # Check date
    today = datetime.datetime.today().date()
    if today != network['active_day']:
        # The date has changed, reset the tally
        network['active_day'] = today
        network['day_tally'] = delta
        return True

    if network['day_tally'] + delta <= int(network["daily_cap"]):
        network['day_tally'] += delta
        return True
    else: 
        return False

async def convert(message, address):
    """
    Provide the balance for a given address and network
    """
    reply = ''
    try:
        reply = export_pub_key(address)
    except Exception:
        reply = '❗ could not handle your request'
        traceback.print_exc()
    await message.reply(reply)


async def request(message, address, network: dict):
    """
    Send tokens to the specified address
    """
    requester = message.author
    # Check whether the faucet has reached the daily cap
    if check_daily_cap(network):
        # Check whether user or address have received tokens on this network
        approved, reply = check_time_limits(requester.id, address, network)
        if approved:
            check = calls.unlock(network["binary"], network['faucet_address'], network['data_dir'], network["node_url"])
            if check:
                try:
                    # Make calls call and send the response back
                    transfer = calls.sendTX(network["binary"], network['faucet_address'], address, network['amount_to_send'], network['data_dir'], network["node_url"])
                    logging.info(f'{requester} requested tokens for {address} in {network["chain_id"]}')
                    now = datetime.datetime.now()
                    if transfer.startswith("\"0x"):
                        await message.reply(f'✅ Hash ID: {transfer}')
                        # Get faucet balance and save to transaction log
                        balance = await getFaucetBalance(network)
                        await export(f'{now.isoformat(timespec="seconds")},'
                            f'{network["chain_id"]},{address},'
                            f'{network["amount_to_send"] + network["denomination"]},'
                            f'{transfer},'
                            f'{balance}'
                        )
                    else:
                        await message.reply(f'❗ request could not be processed\n{transfer}')
                        del activeRequests[network['chain_id']][requester.id]
                        del activeRequests[network['chain_id']][address]
                        network['day_tally'] -= int(network['amount_to_send'])
                except Exception:
                    await message.reply('❗ request could not be processed')
                    traceback.print_exc()
                    del activeRequests[network['chain_id']][requester.id]
                    del activeRequests[network['chain_id']][address]
                    network['day_tally'] -= int(network['amount_to_send'])
            else:
                logging.info(f'Failed to unlock faucet')
                await message.reply('❗ request could not be processed')
        else:
            network['day_tally'] -= int(network['amount_to_send'])
            logging.info(f'{requester} requested tokens for {address} in {network["chain_id"]} and was rejected')
            await message.reply(reply)
    else:
        logging.info(f'{requester} requested tokens for {address} in {network["chain_id"]} but the daily cap has been reached')
        await message.reply("Sorry, the daily cap for this faucet has been reached")

if __name__ == "__main__":
    config = getConfig()
    networks = config["networks"]

    NETWORKS = ""
    if len(networks) > 1:
        NETWORKS = ' ' + '|'.join(list(networks.keys()))
    intents = discord.Intents.all()
    client = discord.Client(intents = intents)

    rq_msg = 'Request tokens through the faucet:\n' \
            f'`$request [0xaddress]{NETWORKS}`\n\n'
    ad_msg = 'Request the faucet address: \n' \
            f'`$faucet_address{NETWORKS}`\n\n'
    bl_msg = 'Request the address balance:\n' \
            f'`$balance [0xaddress]{NETWORKS}`\n\n'
    cv_msg = 'Convert HEX address:\n' \
            f'`$convert [compress_public_key_base64]{NETWORKS}`'

    help_msg = f'**Supported chains:**\n{''.join(f'- {net}\n' for net in list(networks.keys()))}' \
            '\n**List of available commands:**\n' \
            f'1. {rq_msg}' \
            f'2. {ad_msg}' \
            f'3. {bl_msg}' \
            f'4. {cv_msg}'

    @client.event
    async def on_ready():
        """
        Gets called when the Discord client logs in
        """
        logging.info('Logged into Discord as %s', client.user)


    @client.event
    async def on_message(message):
        """
        Responds to messages on specified channels.
        """
        # Only listen in specific channels, and do not listen to your own messages
        print(message.channel.name, config['discord']['channels_to_listen'], message.author)

        if (message.channel.name not in config['discord']['channels_to_listen']) or (message.author == client.user):
            return

        # Respond to $help
        if message.content.startswith('$help'):
            await message.reply(help_msg)
            return

        # Notify users of vega shutdown
        if message.content[0] != ('$') :
            return

        # Respond to commands
        network = ""
        messages = message.content.split()
        if (NETWORKS != ""):
            network = messages[-1]
            if network in list(networks.keys()):
                network = networks[network]
            else: 
                await message.reply(help_msg)
                return
        else: network = networks[list(networks.keys())[0]]

        if messages[0] == '$faucet_address':
            if (NETWORKS != "" and len(messages) == 2) or (NETWORKS == "" and len(messages) == 1):
                await message.reply(f'The {network["chain_id"]} faucet has address `{network["faucet_address"]}`')
            else: await message.reply("Please check again. " + ad_msg)
        elif messages[0] == '$balance':
            if (NETWORKS != "" and len(messages) == 3) or (NETWORKS == "" and len(messages) == 2):
                await getBalance(message, messages[1], network)
            else: await message.reply("Please check again. " + bl_msg)
        elif messages[0] == '$request':
            if (NETWORKS != "" and len(messages) == 3) or (NETWORKS == "" and len(messages) == 2):
                await request(message, messages[1], network)
            else: await message.reply("Please check again. " + rq_msg)
        elif messages[0] == '$convert':
            if (NETWORKS != "" and len(messages) == 3) or (NETWORKS == "" and len(messages) == 2):
                await convert(message, messages[1])
            else: await message.reply("Please check again. " + cv_msg)

    client.run(config["discord"]["bot_token"])