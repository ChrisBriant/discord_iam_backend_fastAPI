from abc import ABC, abstractmethod
#import uuid

class BaseProvider(ABC):
    @abstractmethod
    async def get_auth_url(self, state: str | None):
        pass

    @abstractmethod
    async def exchange_code(self, code: str, state: str | None):
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str):
        pass