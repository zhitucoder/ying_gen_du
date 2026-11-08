from abc import ABC, abstractmethod


class SMSProvider(ABC):
    @abstractmethod
    def send(self, phone: str, code: str, scene: str) -> str:
        """Send an SMS and return the provider message id."""
