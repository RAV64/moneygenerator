def load_correct_creds(creds):
    return creds['prod']['access_key'], creds['prod']['secret_key']


def load_telegram_creds(creds):
    return creds['telegram']['TELEGRAM_CHANNEL_ID'], creds['telegram']['TELEGRAM_TOKEN']
