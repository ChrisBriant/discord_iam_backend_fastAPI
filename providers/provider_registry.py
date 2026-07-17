from .discord_provider import DiscordProvider

def get_provider(provider_name: str):

    providers = {
        'discord' : DiscordProvider(),
    }

    provider = providers.get(provider_name)

    if not provider:
        raise ValueError("Unsupported provider")

    return provider